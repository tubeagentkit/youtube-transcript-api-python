"""HTTP client for the GetYouTubeTranscript REST API.

API reference: https://getyoutubetranscript.com/docs
OpenAPI spec:  https://getyoutubetranscript.com/openapi.json
"""

from __future__ import annotations

import time
from typing import Any, Optional, Sequence

import requests

from .exceptions import GetYouTubeTranscriptError
from .types import BatchData, BatchItem, TranscriptData

DEFAULT_BASE_URL = "https://getyoutubetranscript.com/api/v1"
DEFAULT_TIMEOUT = 30.0


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None`` values so optional query params are omitted entirely."""
    return {k: v for k, v in params.items() if v is not None}


def _send(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
    timeout: float,
) -> dict[str, Any]:
    """Send one HTTP request and return the parsed JSON body.

    Shared by :class:`Client` (authenticated endpoints) and the module-level
    ``signup``/``verify_signup`` helpers (no API key needed), so request
    sending and error parsing live in exactly one place.

    Raises:
        GetYouTubeTranscriptError: on any network failure, non-2xx status, or
            a 2xx response whose body is ``{"success": false, ...}``.
    """
    try:
        response = session.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise GetYouTubeTranscriptError(
            code="NETWORK_ERROR",
            message=str(exc),
            status_code=0,
        ) from exc

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if not response.ok or not isinstance(payload, dict) or payload.get("success") is False:
        code = "UNKNOWN_ERROR"
        message = f"Request failed with HTTP status {response.status_code}"
        if isinstance(payload, dict):
            code = payload.get("code", code)
            message = payload.get("message", message)
        raise GetYouTubeTranscriptError(
            code=code,
            message=message,
            status_code=response.status_code,
            response_body=payload if isinstance(payload, dict) else None,
        )

    return payload


class Client:
    """Authenticated client for the GetYouTubeTranscript API.

    Args:
        api_key: Your API key (``sk_live_...``). Get one free (100 credits,
            no card) at https://getyoutubetranscript.com, or via the
            self-serve :func:`signup` / :func:`verify_signup` flow in this
            module, which needs no key at all.
        base_url: Override the API base URL. Defaults to the production
            endpoint; mainly useful for testing against a local/staging copy.
        timeout: Per-request timeout in seconds.
        session: Bring your own ``requests.Session`` (e.g. for connection
            pooling or custom retry/adapter configuration). One is created
            for you otherwise.

    Every method costs 1 credit unless its docstring says "free" - failed
    and rate-limited requests are never charged. Every method raises
    :class:`~getyoutubetranscript.GetYouTubeTranscriptError` on failure.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return _send(
            self._session,
            "GET",
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=_clean(params),
            timeout=self.timeout,
        )

    def _post(
        self, path: str, body: dict[str, Any], *, extra_headers: Optional[dict[str, str]] = None
    ) -> dict[str, Any]:
        return _send(
            self._session,
            "POST",
            f"{self.base_url}{path}",
            headers={**self._headers(), **(extra_headers or {})},
            json_body=_clean(body),
            timeout=self.timeout,
        )

    # -- transcript -----------------------------------------------------

    def get_transcript(
        self,
        video: str,
        *,
        language: Optional[str] = None,
        timestamps: bool = False,
    ) -> TranscriptData:
        """Get a YouTube video's transcript, plus title/author/thumbnail. 1 credit.

        Args:
            video: Full or short YouTube video URL, or an 11-character video ID.
            language: Caption language code (e.g. ``"en"``, ``"es"``). Defaults
                to the API's default of ``"en"`` when omitted.
            timestamps: When ``True``, also return per-line timing in
                ``segments``. Same 1 credit. The query param is only sent when
                this is ``True``.

        Returns:
            dict with keys ``video_id``, ``language_code`` (the caption track
            actually returned), ``requested_language``, ``caption_type``
            (``"manual"`` for creator captions, ``"auto"`` for speech
            recognition, ``None`` if unknown), ``title``, ``author_name``,
            ``author_url``, ``thumbnail_url``, ``transcript`` (one block of
            text), ``word_count``, ``cached`` and ``fetched_at``. With
            ``timestamps=True`` it also has ``segments``, a list of
            ``{"start": float, "duration": float, "text": str}`` (seconds),
            one per caption line.

        Raises:
            GetYouTubeTranscriptError: e.g. ``code="NOT_FOUND"`` (HTTP 404) if
                the video has no transcript/captions available.
        """
        payload = self._get(
            "/transcript",
            {"v": video, "language": language, "timestamps": "true" if timestamps else None},
        )
        return payload["data"]

    # -- batch --------------------------------------------------------------

    def create_batch(
        self,
        videos: Sequence[str],
        *,
        language: Optional[str] = None,
        timestamps: bool = False,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> BatchData:
        """Queue transcripts for up to 100 videos in one call. Free to submit.

        Returns immediately; transcripts are fetched in the background. 1
        credit is charged per video that returns a transcript, and failed
        videos are never charged. Duplicate videos are fetched once. Follow
        with :meth:`wait_for_batch` (or :meth:`get_batch`), or pass
        ``webhook_url`` to be notified when it finishes.

        Args:
            videos: 1-100 video URLs or 11-character IDs.
            language: Caption language code for every video. Defaults to ``"en"``.
            timestamps: Include per-line ``segments`` in the results.
            webhook_url: Public https URL (port 443) that receives a signed
                ``batch.completed`` POST. Check it with
                :func:`~getyoutubetranscript.verify_webhook_signature` and the
                ``webhook_secret`` returned here.
            idempotency_key: Sent as the ``Idempotency-Key`` header: retrying
                with the same key returns the original batch instead of
                creating (and charging for) a second one.

        Returns:
            dict with ``batch_id``, ``status`` (``"queued"``), counts,
            ``results_url``, and ``webhook_secret`` when ``webhook_url`` was
            given (shown once).

        Raises:
            ValueError: if ``videos`` is empty.
            GetYouTubeTranscriptError: e.g. ``code="TOO_MANY_BATCHES"`` (HTTP
                429) with 5 batches still running, ``code="PAYMENT_REQUIRED"``
                (HTTP 402) with no credits left.
        """
        if not videos:
            raise ValueError("create_batch() requires at least one video")
        payload = self._post(
            "/batch",
            {
                "videos": list(videos),
                "language": language,
                "timestamps": True if timestamps else None,
                "webhook_url": webhook_url,
            },
            extra_headers={"Idempotency-Key": idempotency_key} if idempotency_key else None,
        )
        return payload["data"]

    def get_batch(self, batch_id: str, *, offset: int = 0, limit: int = 20) -> BatchData:
        """Get a batch's status and one page of its results. Free.

        Args:
            batch_id: The ``batch_id`` from :meth:`create_batch`.
            offset: Number of items to skip.
            limit: Items per page, 1-50.

        Returns:
            dict with ``status``, counts, ``credits_charged``, ``items`` (in
            submission order; succeeded items have the same fields as
            :meth:`get_transcript` minus ``cached``, failed items an
            ``error_code``), and ``next_offset`` (``None`` on the last page).

        Raises:
            GetYouTubeTranscriptError: e.g. ``code="NOT_FOUND"`` (HTTP 404) for
                an unknown id or a batch older than 7 days.
        """
        payload = self._get("/batch", {"id": batch_id, "offset": offset, "limit": limit})
        return payload["data"]

    def wait_for_batch(
        self,
        batch_id: str,
        *,
        poll_interval: float = 3.0,
        timeout: float = 900.0,
        page_size: int = 50,
    ) -> BatchData:
        """Poll until a batch completes, then return it with every item. Free.

        Args:
            batch_id: The ``batch_id`` from :meth:`create_batch`.
            poll_interval: Seconds between status checks.
            timeout: Give up after this many seconds.
            page_size: Items fetched per request once complete, 1-50.

        Returns:
            The batch dict from :meth:`get_batch`, with ``items`` holding all
            items and ``next_offset`` set to ``None``.

        Raises:
            TimeoutError: if the batch hasn't completed within ``timeout``.
            GetYouTubeTranscriptError: on API failure.
        """
        deadline = time.monotonic() + timeout
        batch = self.get_batch(batch_id, limit=1)
        while batch["status"] != "completed":
            if time.monotonic() >= deadline:
                raise TimeoutError(f"batch {batch_id} not completed after {timeout:g}s ({batch['pending']} pending)")
            time.sleep(poll_interval)
            batch = self.get_batch(batch_id, limit=1)

        items: list[BatchItem] = []
        offset: Optional[int] = 0
        while offset is not None:
            page = self.get_batch(batch_id, offset=offset, limit=page_size)
            items.extend(page["items"])
            offset = page["next_offset"]
            batch = page
        return {**batch, "items": items, "next_offset": None}

    # -- search -----------------------------------------------------------

    def search(
        self,
        query: Optional[str] = None,
        *,
        page_token: Optional[str] = None,
        type: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Search YouTube for videos or channels. 1 credit.

        Args:
            query: Search query. Required for a first page unless
                ``page_token`` is given.
            page_token: The ``continuation_token`` from a previous response,
                to fetch the next page. Treat as opaque - don't construct it
                yourself. Expires after 24 hours.
            type: Restrict results to ``"video"`` (default) or ``"channel"``.
                Never mixes both kinds in one response.
            country: Two-letter region code, e.g. ``"us"``.
            language: Result language hint, e.g. ``"en"``.
            limit: Max results to return for this page.

        Returns:
            dict with ``query``, and either ``video_results`` or
            ``channel_results`` depending on ``type``, plus
            ``continuation_token`` for the next page (missing or ``None`` when
            there are no more pages, so read it with ``.get()``).

        Raises:
            ValueError: if neither ``query`` nor ``page_token`` is given.
            GetYouTubeTranscriptError: on API failure.
        """
        if not query and not page_token:
            raise ValueError("search() requires either 'query' or 'page_token'")
        payload = self._get(
            "/search",
            {
                "q": query,
                "page_token": page_token,
                "type": type,
                "country": country,
                "language": language,
                "limit": limit,
            },
        )
        return payload["data"]

    # -- channels -----------------------------------------------------------

    def resolve_channel(self, handle: str) -> dict[str, Any]:
        """Resolve a channel @handle, URL, or ``UC...`` id to its channel ID. Free.

        Args:
            handle: Channel ``@handle``, a channel URL, or an existing
                ``UC...`` channel id.

        Returns:
            dict with ``channel_id``, ``title``, ``handle``, ``resolved_via``.

        Raises:
            GetYouTubeTranscriptError: e.g. ``code="NOT_FOUND"`` (HTTP 404) if
                no channel matches.
        """
        payload = self._get("/resolve", {"handle": handle})
        return payload["data"]

    def get_channel_latest(self, channel: str) -> dict[str, Any]:
        """Get a channel's metadata plus its home-tab "Latest Videos" shelf. Free.

        For the complete, paginated upload history use
        :meth:`list_channel_videos` instead.

        Args:
            channel: Channel ``@handle``, URL, or ``UC...`` id.

        Returns:
            dict of channel metadata plus a home-tab video shelf. The exact
            field set is passed through from upstream and may grow over
            time - treat it as loosely typed.

        Raises:
            GetYouTubeTranscriptError: e.g. ``code="NOT_FOUND"`` (HTTP 404) if
                the channel doesn't exist.
        """
        payload = self._get("/channel/latest", {"channel": channel})
        return payload["data"]

    def search_channel(
        self,
        channel: Optional[str] = None,
        query: Optional[str] = None,
        *,
        continuation: Optional[str] = None,
    ) -> dict[str, Any]:
        """Search within one channel's videos. 1 credit.

        Args:
            channel: Channel ``@handle``, URL, or ``UC...`` id. Required for a
                first page unless ``continuation`` is given.
            query: Query to search within the channel. Required for a first
                page unless ``continuation`` is given.
            continuation: Continuation token from a previous response's
                ``continuation_token``, to fetch the next page.

        Returns:
            dict with ``videos`` (list), ``has_more`` (bool), and
            ``continuation_token`` (present when ``has_more`` is true).

        Raises:
            ValueError: if ``continuation`` is not given and either
                ``channel`` or ``query`` is missing.
            GetYouTubeTranscriptError: on API failure.
        """
        if not continuation and (not channel or not query):
            raise ValueError(
                "search_channel() requires either 'continuation', or both "
                "'channel' and 'query'"
            )
        payload = self._get(
            "/channel/search",
            {"channel": channel, "q": query, "continuation": continuation},
        )
        return payload["data"]

    def list_channel_videos(
        self, channel: Optional[str] = None, *, continuation: Optional[str] = None
    ) -> dict[str, Any]:
        """List every video a channel has ever uploaded (paginated). 1 credit.

        This is the channel's full ``/videos`` tab - not just the home-tab
        shelf :meth:`get_channel_latest` returns.

        Args:
            channel: Channel ``@handle``, URL, or ``UC...`` id. Required for a
                first page unless ``continuation`` is given.
            continuation: Continuation token from a previous response's
                ``continuation_token``, to fetch the next page.

        Returns:
            dict with ``videos`` (list), ``has_more`` (bool), and
            ``continuation_token`` (present when ``has_more`` is true).

        Raises:
            ValueError: if neither ``channel`` nor ``continuation`` is given.
            GetYouTubeTranscriptError: e.g. ``code="NOT_FOUND"`` (HTTP 404) if
                the channel doesn't exist.
        """
        if not channel and not continuation:
            raise ValueError(
                "list_channel_videos() requires either 'channel' or 'continuation'"
            )
        payload = self._get(
            "/channel/videos", {"channel": channel, "continuation": continuation}
        )
        return payload["data"]

    # -- playlists -----------------------------------------------------------

    def get_playlist(
        self, list_id: Optional[str] = None, *, continuation: Optional[str] = None
    ) -> dict[str, Any]:
        """List every video in a playlist (paginated). 1 credit.

        Args:
            list_id: Playlist ID or URL. Required for a first page unless
                ``continuation`` is given.
            continuation: Continuation token from a previous response's
                ``continuation_token``, to fetch the next page.

        Returns:
            dict with ``playlist_id``, ``title``, ``videos`` (list),
            ``has_more`` (bool), and ``continuation_token`` (present when
            ``has_more`` is true).

        Raises:
            ValueError: if neither ``list_id`` nor ``continuation`` is given.
            GetYouTubeTranscriptError: e.g. ``code="NOT_FOUND"`` (HTTP 404) if
                the playlist is missing, private, or deleted.
        """
        if not list_id and not continuation:
            raise ValueError("get_playlist() requires either 'list_id' or 'continuation'")
        payload = self._get("/playlist", {"list": list_id, "continuation": continuation})
        return payload["data"]

    # -- account -----------------------------------------------------------

    def get_credits(self) -> dict[str, Any]:
        """Check the remaining credit balance and plan for this API key. Free.

        Returns:
            dict with ``plan_credits_left``, ``topup_credits_left``, ``plan``
            (one of ``"free"``, ``"monthly"``, ``"yearly"``), and
            ``rate_limit_per_minute``.

        Raises:
            GetYouTubeTranscriptError: e.g. ``code="MISSING_API_KEY"``
                (HTTP 401) if no API key is provided.
        """
        payload = self._get("/credits", {})
        return payload["data"]


# -- self-serve signup, no API key required --------------------------------


def signup(
    email: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> str:
    """Request a 6-digit email OTP to create or access an API key. Free, no key needed.

    Step 1 of the self-serve signup flow. Follow with :func:`verify_signup`
    once the caller has the code from their inbox. The code is valid for 10
    minutes.

    Args:
        email: Address to send the one-time code to.
        base_url: Override the API base URL.
        timeout: Request timeout in seconds.
        session: Optional ``requests.Session`` to reuse.

    Returns:
        The confirmation message string from the API.

    Raises:
        GetYouTubeTranscriptError: e.g. ``code="BAD_REQUEST"`` (HTTP 400) if
            the email is missing or malformed.
    """
    payload = _send(
        session or requests.Session(),
        "POST",
        f"{base_url.rstrip('/')}/signup",
        json_body={"email": email},
        timeout=timeout,
    )
    return payload.get("message", "")


def verify_signup(
    email: str,
    otp: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> str:
    """Verify the OTP from :func:`signup` and mint a fresh API key. Free, no key needed.

    Step 2 of the self-serve signup flow. Creates the account if it doesn't
    exist yet, or signs in an existing one, either way returning a freshly
    minted API key.

    Args:
        email: The same address passed to :func:`signup`.
        otp: The 6-digit code the caller received by email.
        base_url: Override the API base URL.
        timeout: Request timeout in seconds.
        session: Optional ``requests.Session`` to reuse.

    Returns:
        The raw API key string (``sk_live_...``). It is shown once here and
        cannot be retrieved again - the caller is responsible for storing it.

    Raises:
        GetYouTubeTranscriptError: e.g. ``code="BAD_REQUEST"`` (HTTP 400) if
            fields are missing or the code is invalid/expired.
    """
    payload = _send(
        session or requests.Session(),
        "POST",
        f"{base_url.rstrip('/')}/signup/verify",
        json_body={"email": email, "otp": otp},
        timeout=timeout,
    )
    return payload["api_key"]
