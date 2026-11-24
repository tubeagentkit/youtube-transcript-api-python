"""Unit tests for AI transcripts: ``mode``, 202 jobs and polling.

All HTTP is mocked with ``responses``; no network, key or credits needed.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import responses

from getyoutubetranscript import Client, GetYouTubeTranscriptError

BASE_URL = "https://getyoutubetranscript.com/api/v1"
JOB_ID = "6f1c2b0e-8a4d-4c1e-9b7a-2d3e4f5a6b7c"

AI_DATA = {
    "video_id": "jNQXAC9IVRw",
    "language_code": "en",
    "requested_language": "en",
    "caption_type": "ai",
    "title": "Me at the zoo",
    "author_name": "jawed",
    "author_url": "u",
    "thumbnail_url": "th",
    "transcript": "All right, so here we are",
    "word_count": 6,
    "fetched_at": "2026-09-20T03:10:58.938Z",
    "source": "ai",
    "duration_seconds": 19,
}


def _job(status: str, **extra) -> dict:
    return {
        "job_id": JOB_ID,
        "status": status,
        "video_id": "jNQXAC9IVRw",
        "credits_charged": 3,
        "poll_url": f"/api/v1/transcript/jobs?id={JOB_ID}",
        "poll_interval_seconds": 5,
        "created_at": "2026-09-20T03:10:58.938Z",
        **extra,
    }


def _query(request) -> dict[str, list[str]]:
    return parse_qs(urlparse(request.url).query)


@pytest.fixture
def client() -> Client:
    return Client(api_key="sk_live_test_key")


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("getyoutubetranscript.client.time.sleep", sleeps.append)
    return sleeps


@responses.activate
def test_get_transcript_sends_mode_and_returns_ai_fields(client: Client):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript", json={"success": True, "data": AI_DATA},
        headers={"X-Credits-Charged": "3"}, status=200,
    )

    result = client.get_transcript("jNQXAC9IVRw", mode="generate")

    assert _query(responses.calls[0].request)["mode"] == ["generate"]
    assert len(responses.calls) == 1
    assert result["caption_type"] == "ai"
    assert result["source"] == "ai"
    assert result["duration_seconds"] == 19


@responses.activate
def test_get_transcript_omits_mode_by_default(client: Client):
    responses.add(responses.GET, f"{BASE_URL}/transcript", json={"success": True, "data": AI_DATA}, status=200)
    client.get_transcript("jNQXAC9IVRw")
    assert "mode" not in _query(responses.calls[0].request)


@responses.activate
def test_start_transcript_returns_job_and_credits_without_polling(client: Client):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript",
        json={"success": True, "data": None, "job": _job("running")},
        headers={"X-Credits-Charged": "12"}, status=202,
    )

    result = client.start_transcript("dQw4w9WgXcQ", mode="auto")

    assert len(responses.calls) == 1
    assert result["data"] is None
    assert result["job"]["job_id"] == JOB_ID
    assert result["credits_charged"] == 12


@responses.activate
def test_start_transcript_credits_none_without_header(client: Client):
    responses.add(responses.GET, f"{BASE_URL}/transcript", json={"success": True, "data": AI_DATA}, status=200)
    result = client.start_transcript("jNQXAC9IVRw")
    assert result["credits_charged"] is None
    assert "job" not in result
    assert result["data"]["transcript"] == "All right, so here we are"


@responses.activate
def test_get_transcript_polls_job_after_202(client: Client, no_sleep):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript",
        json={"success": True, "data": None, "job": _job("queued")}, status=202,
    )
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": True, "data": None, "job": _job("running")}, status=202,
    )
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": True, "data": {**AI_DATA, "segments": []}, "job": _job("done")}, status=200,
    )

    result = client.get_transcript("jNQXAC9IVRw", mode="generate", timestamps=True)

    assert result["source"] == "ai"
    assert result["segments"] == []
    assert len(responses.calls) == 3
    poll = _query(responses.calls[1].request)
    assert poll["id"] == [JOB_ID]
    assert poll["timestamps"] == ["true"]
    assert no_sleep == [5.0]  # the job's poll_interval_seconds


@responses.activate
def test_get_transcript_job_returns_none_data_while_running(client: Client):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": True, "data": None, "job": _job("running")}, status=202,
    )

    result = client.get_transcript_job(JOB_ID)

    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer sk_live_test_key"
    assert _query(req) == {"id": [JOB_ID]}
    assert result["data"] is None
    assert result["job"]["status"] == "running"


@responses.activate
def test_wait_for_transcript_raises_job_error(client: Client, no_sleep):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": False, "code": "AI_FAILED", "message": "Could not make the transcript.", "job": _job("failed")},
        status=502,
    )
    with pytest.raises(GetYouTubeTranscriptError) as excinfo:
        client.wait_for_transcript(JOB_ID)
    assert excinfo.value.code == "AI_FAILED"
    assert excinfo.value.status_code == 502


@responses.activate
def test_wait_for_transcript_raises_on_failed_status(client: Client, no_sleep):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": True, "data": None, "job": _job("failed", error={"code": "AUDIO_UNAVAILABLE", "message": "No audio."})},
        status=202,
    )
    with pytest.raises(GetYouTubeTranscriptError) as excinfo:
        client.wait_for_transcript(_job("running"))
    assert excinfo.value.code == "AUDIO_UNAVAILABLE"


@responses.activate
def test_wait_for_transcript_times_out(client: Client):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": True, "data": None, "job": _job("running")}, status=202,
    )
    with pytest.raises(TimeoutError, match=JOB_ID):
        client.wait_for_transcript(JOB_ID, poll_interval=0, timeout=0)
    assert len(responses.calls) == 1


@responses.activate
def test_payment_required_exposes_credits_required(client: Client):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript",
        json={"success": False, "code": "PAYMENT_REQUIRED", "message": "You have used all your credits.", "credits_required": 12},
        status=402,
    )
    with pytest.raises(GetYouTubeTranscriptError) as excinfo:
        client.get_transcript("dQw4w9WgXcQ", mode="generate")
    assert excinfo.value.code == "PAYMENT_REQUIRED"
    assert excinfo.value.credits_required == 12


@responses.activate
def test_job_not_found(client: Client):
    responses.add(
        responses.GET, f"{BASE_URL}/transcript/jobs",
        json={"success": False, "code": "JOB_NOT_FOUND", "message": "No AI transcript job with this id."},
        status=404,
    )
    with pytest.raises(GetYouTubeTranscriptError) as excinfo:
        client.get_transcript_job(JOB_ID)
    assert excinfo.value.code == "JOB_NOT_FOUND"
    assert excinfo.value.status_code == 404
