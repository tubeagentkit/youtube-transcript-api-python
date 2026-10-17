"""Unit tests: request construction, auth headers, and error parsing.

These never touch the network - all HTTP is mocked with ``responses``. They
must always pass in CI with no API key or credits required.
"""

from __future__ import annotations

import pytest
import responses

from getyoutubetranscript import Client, GetYouTubeTranscriptError, signup, verify_signup

BASE_URL = "https://getyoutubetranscript.com/api/v1"


@pytest.fixture
def client() -> Client:
    return Client(api_key="sk_live_test_key")


# -- construction --------------------------------------------------------


def test_requires_api_key():
    with pytest.raises(ValueError):
        Client(api_key="")


def test_strips_trailing_slash_from_base_url():
    c = Client(api_key="k", base_url="https://example.com/api/v1/")
    assert c.base_url == "https://example.com/api/v1"


# -- request construction & auth header ----------------------------------


@responses.activate
def test_get_transcript_sends_bearer_auth_header_and_params(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={
            "success": True,
            "data": {
                "video_id": "jNQXAC9IVRw",
                "language_code": "en",
                "title": "Me at the zoo",
                "author_name": "jawed",
                "author_url": "https://www.youtube.com/channel/UC4QobU6STFB0P71PVoOGeMg",
                "thumbnail_url": "https://i.ytimg.com/vi/jNQXAC9IVRw/hqdefault.jpg",
                "transcript": "All right, so here we are...",
                "word_count": 6,
            },
        },
        status=200,
    )

    result = client.get_transcript("jNQXAC9IVRw", language="en")

    assert result["transcript"] == "All right, so here we are..."
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk_live_test_key"
    assert "v=jNQXAC9IVRw" in req.url
    assert "language=en" in req.url


@responses.activate
def test_get_transcript_timestamps_sends_param_and_returns_segments(client: Client):
    segments = [{"start": 3.96, "duration": 4.56, "text": "So, Reed, education"}]
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={
            "success": True,
            "data": {"transcript": "So, Reed, education", "segments": segments},
        },
        status=200,
    )

    result = client.get_transcript("5e37ZT3SQbk", language="en", timestamps=True)

    req = responses.calls[0].request
    assert "timestamps=true" in req.url
    assert result["segments"] == segments


@responses.activate
def test_get_transcript_omits_timestamps_by_default_and_when_false(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={"success": True, "data": {"transcript": "hi"}},
        status=200,
    )

    result = client.get_transcript("jNQXAC9IVRw")
    client.get_transcript("jNQXAC9IVRw", timestamps=False)

    assert "timestamps" not in responses.calls[0].request.url
    assert "timestamps" not in responses.calls[1].request.url
    assert "segments" not in result


@responses.activate
def test_get_transcript_omits_optional_language_when_not_given(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={"success": True, "data": {"transcript": "hi"}},
        status=200,
    )

    client.get_transcript("jNQXAC9IVRw")

    req = responses.calls[0].request
    assert "language" not in req.url


@responses.activate
def test_search_by_query(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/search",
        json={
            "success": True,
            "data": {"query": "lofi beats", "video_results": [{"videoId": "jfKfPfyJRdk"}]},
        },
        status=200,
    )

    result = client.search("lofi beats", type="video", limit=5)

    assert result["video_results"][0]["videoId"] == "jfKfPfyJRdk"
    req = responses.calls[0].request
    assert "q=lofi+beats" in req.url or "q=lofi%20beats" in req.url
    assert "type=video" in req.url
    assert "limit=5" in req.url


def test_search_requires_query_or_page_token(client: Client):
    with pytest.raises(ValueError):
        client.search()


@responses.activate
def test_search_by_page_token(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/search",
        json={"success": True, "data": {"video_results": []}},
        status=200,
    )
    client.search(page_token="CBkSDBIKMjAyM")
    req = responses.calls[0].request
    assert "page_token=CBkSDBIKMjAyM" in req.url
    assert "q=" not in req.url


@responses.activate
def test_resolve_channel_calls_resolve_endpoint(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/resolve",
        json={
            "success": True,
            "data": {
                "channel_id": "UCBJycsmduvYEL83R_U4JriQ",
                "title": "Marques Brownlee",
                "handle": "http://www.youtube.com/@mkbhd",
                "resolved_via": "scrape",
            },
        },
        status=200,
    )

    result = client.resolve_channel("@mkbhd")

    assert result["channel_id"] == "UCBJycsmduvYEL83R_U4JriQ"
    assert "handle=%40mkbhd" in responses.calls[0].request.url


@responses.activate
def test_get_channel_latest(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/channel/latest",
        json={"success": True, "data": {"title": "MKBHD"}},
        status=200,
    )
    result = client.get_channel_latest("@mkbhd")
    assert result["title"] == "MKBHD"


def test_search_channel_requires_channel_and_query_or_continuation(client: Client):
    with pytest.raises(ValueError):
        client.search_channel()
    with pytest.raises(ValueError):
        client.search_channel(channel="@mkbhd")
    with pytest.raises(ValueError):
        client.search_channel(query="iphone")


@responses.activate
def test_search_channel_with_continuation_only(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/channel/search",
        json={"success": True, "data": {"videos": [], "has_more": False}},
        status=200,
    )
    client.search_channel(continuation="EqAA...")
    assert "continuation=EqAA" in responses.calls[0].request.url


def test_list_channel_videos_requires_channel_or_continuation(client: Client):
    with pytest.raises(ValueError):
        client.list_channel_videos()


@responses.activate
def test_list_channel_videos(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/channel/videos",
        json={"success": True, "data": {"videos": [], "has_more": False}},
        status=200,
    )
    client.list_channel_videos(channel="@TED")


def test_get_playlist_requires_list_id_or_continuation(client: Client):
    with pytest.raises(ValueError):
        client.get_playlist()


@responses.activate
def test_get_playlist_by_id(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/playlist",
        json={
            "success": True,
            "data": {"playlist_id": "PLillGF-RfqbYE6Ik_EuXA2iZFcE082B3s", "videos": []},
        },
        status=200,
    )
    result = client.get_playlist("PLillGF-RfqbYE6Ik_EuXA2iZFcE082B3s")
    assert result["playlist_id"] == "PLillGF-RfqbYE6Ik_EuXA2iZFcE082B3s"


@responses.activate
def test_get_credits_is_free_endpoint(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/credits",
        json={
            "success": True,
            "data": {
                "plan_credits_left": 87,
                "topup_credits_left": 0,
                "plan": "monthly",
                "rate_limit_per_minute": 200,
            },
        },
        status=200,
    )

    result = client.get_credits()

    assert result["plan"] == "monthly"
    assert result["plan_credits_left"] == 87
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk_live_test_key"
    assert req.url == f"{BASE_URL}/credits"


# -- error parsing --------------------------------------------------------


@responses.activate
def test_missing_api_key_error_parsed(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={
            "success": False,
            "code": "MISSING_API_KEY",
            "message": "Provide an API key via the Authorization: Bearer header or the x-api-key header.",
        },
        status=401,
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.get_transcript("jNQXAC9IVRw")

    err = exc_info.value
    assert err.code == "MISSING_API_KEY"
    assert err.status_code == 401
    assert "Authorization" in err.message


@responses.activate
def test_rate_limited_error_exposes_extra_fields(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/search",
        json={
            "success": False,
            "code": "RATE_LIMITED",
            "message": "Rate limit exceeded for your plan tier.",
            "requestsThisMinute": 61,
        },
        status=429,
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.search("lofi")

    err = exc_info.value
    assert err.code == "RATE_LIMITED"
    assert err.status_code == 429
    assert err.response_body["requestsThisMinute"] == 61


@responses.activate
def test_payment_required_error(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={
            "success": False,
            "code": "PAYMENT_REQUIRED",
            "message": "You have used all your credits.",
            "creditsLeft": 0,
        },
        status=402,
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.get_transcript("jNQXAC9IVRw")

    assert exc_info.value.code == "PAYMENT_REQUIRED"
    assert exc_info.value.status_code == 402


@responses.activate
def test_not_found_error(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={"success": False, "code": "NOT_FOUND", "message": "No transcript found."},
        status=404,
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.get_transcript("no_captions_video")

    assert exc_info.value.status_code == 404


@responses.activate
def test_non_json_error_body_falls_back_to_generic_message(client: Client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        body="<html>502 Bad Gateway</html>",
        status=502,
        content_type="text/html",
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.get_transcript("jNQXAC9IVRw")

    err = exc_info.value
    assert err.status_code == 502
    assert err.code == "UNKNOWN_ERROR"


@responses.activate
def test_success_false_with_200_status_still_raises(client: Client):
    # Defensive: even if a proxy/edge case ever returns 200 with success=false,
    # the SDK must still raise rather than silently returning bad data.
    responses.add(
        responses.GET,
        f"{BASE_URL}/transcript",
        json={"success": False, "code": "WEIRD_STATE", "message": "huh"},
        status=200,
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.get_transcript("jNQXAC9IVRw")

    assert exc_info.value.code == "WEIRD_STATE"


@responses.activate
def test_network_error_wrapped(client: Client, monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(client._session, "request", boom)

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        client.get_transcript("jNQXAC9IVRw")

    assert exc_info.value.code == "NETWORK_ERROR"
    assert exc_info.value.status_code == 0


# -- signup / verify_signup (no api key) ----------------------------------


@responses.activate
def test_signup_sends_email_no_auth_header():
    responses.add(
        responses.POST,
        f"{BASE_URL}/signup",
        json={"success": True, "message": "A 6-digit code was sent to this email."},
        status=200,
    )

    message = signup("dev@example.com")

    assert "6-digit code" in message
    req = responses.calls[0].request
    assert "Authorization" not in req.headers
    assert req.body is not None
    import json as _json

    assert _json.loads(req.body) == {"email": "dev@example.com"}


@responses.activate
def test_verify_signup_returns_api_key():
    responses.add(
        responses.POST,
        f"{BASE_URL}/signup/verify",
        json={"success": True, "api_key": "sk_live_abc123"},
        status=200,
    )

    api_key = verify_signup("dev@example.com", "123456")

    assert api_key == "sk_live_abc123"


@responses.activate
def test_signup_invalid_email_raises():
    responses.add(
        responses.POST,
        f"{BASE_URL}/signup",
        json={"success": False, "code": "BAD_REQUEST", "message": "Invalid email."},
        status=400,
    )

    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        signup("not-an-email")

    assert exc_info.value.code == "BAD_REQUEST"


@responses.activate
def test_verify_signup_invalid_otp_raises():
    responses.add(
        responses.POST,
        f"{BASE_URL}/signup/verify",
        json={"success": False, "code": "BAD_REQUEST", "message": "Invalid or expired code."},
        status=400,
    )

    with pytest.raises(GetYouTubeTranscriptError):
        verify_signup("dev@example.com", "000000")
