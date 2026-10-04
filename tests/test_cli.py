"""Unit tests for the command line (client is faked, no network)."""

from __future__ import annotations

import json

import pytest

from getyoutubetranscript import GetYouTubeTranscriptError
from getyoutubetranscript.cli import API_KEY_ENV, main

SEGMENTS = [{"start": 0.0, "duration": 1.0, "text": "hi"}]


class FakeClient:
    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)

    def get_transcript(self, video, *, language=None, timestamps=False):
        self.calls.append({"video": video, "language": language, "timestamps": timestamps})
        if video in self.fail:
            raise GetYouTubeTranscriptError("NOT_FOUND", "No transcript for this video.", 404)
        data = {"video_id": video, "language_code": language or "en", "transcript": f"text of {video}"}
        if timestamps:
            data["segments"] = SEGMENTS
        return data


def test_text_to_stdout_without_timestamps(capsys):
    client = FakeClient()
    assert main(["vid1"], client=client) == 0
    assert capsys.readouterr().out == "text of vid1\n"
    assert client.calls == [{"video": "vid1", "language": None, "timestamps": False}]


def test_srt_requests_timestamps_and_passes_language(capsys):
    client = FakeClient()
    assert main(["vid1", "-f", "srt", "-l", "es"], client=client) == 0
    assert capsys.readouterr().out == "1\n00:00:00,000 --> 00:00:01,000\nhi\n\n"
    assert client.calls[0] == {"video": "vid1", "language": "es", "timestamps": True}


def test_json_for_several_videos_is_one_list(capsys):
    assert main(["a", "b", "-f", "json"], client=FakeClient()) == 0
    out = json.loads(capsys.readouterr().out)
    assert [item["video_id"] for item in out] == ["a", "b"]
    assert out[0]["segments"] == SEGMENTS


def test_output_dir_writes_one_file_per_video(tmp_path):
    assert main(["a", "b", "-f", "vtt", "-o", str(tmp_path)], client=FakeClient()) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.vtt", "b.vtt"]
    assert (tmp_path / "a.vtt").read_text(encoding="utf-8").startswith("WEBVTT\n\n00:00:00.000")


def test_timed_files_use_txt_extension(tmp_path):
    assert main(["a", "-f", "timed", "-o", str(tmp_path)], client=FakeClient()) == 0
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "[0:00] hi"


def test_several_srt_videos_need_output_dir(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["a", "b", "-f", "srt"], client=FakeClient())
    assert exit_info.value.code == 2
    assert "--output-dir" in capsys.readouterr().err


def test_keeps_going_after_a_failure_and_exits_1(capsys):
    assert main(["bad", "good"], client=FakeClient(fail={"bad"})) == 1
    captured = capsys.readouterr()
    assert captured.out == "text of good\n"
    assert "bad: No transcript for this video. (NOT_FOUND)" in captured.err


def test_missing_api_key_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(SystemExit) as exit_info:
        main(["vid1"])
    assert exit_info.value.code == 2
    assert API_KEY_ENV in capsys.readouterr().err


def test_pipe_closed_early_exits_quietly(monkeypatch, tmp_path):
    import getyoutubetranscript.cli as cli

    def broken_pipe(*args, **kwargs):
        raise BrokenPipeError

    monkeypatch.setattr(cli, "_run", broken_pipe)
    out = (tmp_path / "out").open("w")
    monkeypatch.setattr("sys.stdout", out)
    assert cli.main(["vid1"]) == 0
