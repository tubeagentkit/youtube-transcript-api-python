"""Live integration tests against the real GetYouTubeTranscript API.

Skipped entirely unless ``GYT_API_KEY`` is set in the environment - these are
never run in normal CI and never require network access or credits to pass
the rest of the suite.

To run these yourself:

    export GYT_API_KEY=sk_live_...
    pytest tests/live -v

Credit cost per run: the two paid tests below (``get_transcript``,
``search``) each spend 1 credit. The channel and credits tests are free
endpoints. If you're testing against a shared/limited key, run a subset
with ``pytest tests/live -k transcript`` etc.
"""

from __future__ import annotations

import os

import pytest

from getyoutubetranscript import Client, GetYouTubeTranscriptError

API_KEY = os.environ.get("GYT_API_KEY")

pytestmark = pytest.mark.skipif(
    not API_KEY, reason="Set GYT_API_KEY to run live integration tests"
)

# A stable, always-available public video: the first video ever uploaded to
# YouTube. Good for repeated live testing since it will never be deleted or
# have its captions removed.
KNOWN_VIDEO_ID = "jNQXAC9IVRw"
KNOWN_CHANNEL_HANDLE = "@mkbhd"


@pytest.fixture
def client() -> Client:
    assert API_KEY is not None
    return Client(api_key=API_KEY)


def test_resolve_channel_live(client: Client):
    """Free endpoint - safe to run often."""
    result = client.resolve_channel(KNOWN_CHANNEL_HANDLE)
    assert result["channel_id"].startswith("UC")
    assert result["title"]


def test_get_channel_latest_live(client: Client):
    """Free endpoint - safe to run often."""
    result = client.get_channel_latest(KNOWN_CHANNEL_HANDLE)
    assert isinstance(result, dict)
    assert result


def test_get_transcript_live(client: Client):
    """Paid endpoint (1 credit) - confirms the end-to-end transcript shape."""
    result = client.get_transcript(KNOWN_VIDEO_ID)
    assert result["video_id"] == KNOWN_VIDEO_ID
    assert result["transcript"]
    assert result["word_count"] > 0


def test_search_live(client: Client):
    """Paid endpoint (1 credit) - confirms the end-to-end search shape."""
    result = client.search("lofi hip hop", type="video", limit=5)
    assert "video_results" in result
    assert len(result["video_results"]) > 0


def test_search_pagination_live(client: Client):
    """The README pagination example: continuation_token goes back in as page_token."""
    first_page = client.search("lofi beats", type="video", limit=10)
    assert "pagination" not in first_page
    token = first_page.get("continuation_token")
    assert token, "first page should offer a next page"
    page2 = client.search(page_token=token)
    assert page2["video_results"]
    first_titles = {v.get("title") for v in first_page["video_results"]}
    assert not first_titles & {v.get("title") for v in page2["video_results"]}


def test_get_credits_live(client: Client):
    """Free endpoint - safe to run often."""
    result = client.get_credits()
    assert result["plan"] in ("free", "monthly", "yearly")
    assert isinstance(result["plan_credits_left"], int)
    assert isinstance(result["rate_limit_per_minute"], int)


def test_invalid_api_key_raises_typed_error():
    """No credits spent - the request is rejected before authentication succeeds."""
    bad_client = Client(api_key="sk_live_definitely_invalid_key_00000")
    with pytest.raises(GetYouTubeTranscriptError) as exc_info:
        bad_client.resolve_channel(KNOWN_CHANNEL_HANDLE)
    assert exc_info.value.status_code == 401
