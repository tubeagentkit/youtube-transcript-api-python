"""Unit tests for the transcript formatters (no network)."""

from __future__ import annotations

import json

import pytest

from getyoutubetranscript import format_transcript, to_json, to_srt, to_text, to_timed_text, to_vtt

DATA = {
    "video_id": "abc12345678",
    "language_code": "en",
    "title": "A video",
    "author_name": "A channel",
    "transcript": "hello world. café --> next",
    "word_count": 5,
    "segments": [
        {"start": 0.0, "duration": 2.5, "text": "hello world."},
        {"start": 1.9996, "duration": 1.0, "text": "café --> next"},
        {"start": 3725.25, "duration": 4.0, "text": " an hour in "},
    ],
}
NO_SEGMENTS = {k: v for k, v in DATA.items() if k != "segments"}


def test_text_is_the_plain_transcript():
    assert to_text(DATA) == "hello world. café --> next"
    assert to_text(NO_SEGMENTS) == "hello world. café --> next"


def test_timed_text_uses_player_clock():
    assert to_timed_text(DATA).splitlines() == [
        "[0:00] hello world.",
        "[0:01] café --> next",
        "[1:02:05] an hour in",
    ]


def test_srt_cues_numbering_and_rounding():
    assert to_srt(DATA) == (
        "1\n00:00:00,000 --> 00:00:02,500\nhello world.\n\n"
        # 1.9996s rounds to 2.000s, never "00:00:01,1000"
        "2\n00:00:02,000 --> 00:00:03,000\ncafé --> next\n\n"
        "3\n01:02:05,250 --> 01:02:09,250\nan hour in\n"
    )


def test_vtt_header_dot_millis_and_escaped_arrow():
    assert to_vtt(DATA) == (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.500\nhello world.\n\n"
        "00:00:02.000 --> 00:00:03.000\ncafé --&gt; next\n\n"
        "01:02:05.250 --> 01:02:09.250\nan hour in\n"
    )


def test_json_round_trips_and_keeps_unicode():
    out = to_json(DATA)
    assert json.loads(out) == DATA
    assert "café" in out


@pytest.mark.parametrize("fn", [to_srt, to_vtt, to_timed_text])
def test_timed_formats_explain_missing_segments(fn):
    with pytest.raises(ValueError, match="timestamps=True"):
        fn(NO_SEGMENTS)


def test_format_transcript_dispatches_and_rejects_unknown():
    assert format_transcript(DATA, "srt") == to_srt(DATA)
    with pytest.raises(ValueError, match="Unknown format"):
        format_transcript(DATA, "docx")
