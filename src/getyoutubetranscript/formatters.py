"""Turn a transcript from :meth:`Client.get_transcript` into text, timed text, JSON, SRT or WebVTT.

    from getyoutubetranscript import Client
    from getyoutubetranscript.formatters import to_srt

    result = client.get_transcript("jNQXAC9IVRw", timestamps=True)
    open("video.srt", "w", encoding="utf-8").write(to_srt(result))

Timed text, SRT and WebVTT need per-line timing, so fetch with ``timestamps=True``.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Mapping

from .types import Segment

FORMATS = ("text", "timed", "json", "srt", "vtt")
TIMED_FORMATS = ("timed", "srt", "vtt")


def _segments(data: Mapping[str, Any]) -> List[Segment]:
    segments = data.get("segments")
    if not segments:
        raise ValueError(
            "This format needs per-line timing. Fetch the transcript with timestamps=True."
        )
    return segments


def _clock(seconds: float, decimal_mark: str) -> str:
    millis = max(0, int(round(seconds * 1000)))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_mark}{millis:03d}"


def _cues(data: Mapping[str, Any], decimal_mark: str) -> List[str]:
    cues = []
    for segment in _segments(data):
        start = float(segment["start"])
        end = start + float(segment["duration"])
        timing = f"{_clock(start, decimal_mark)} --> {_clock(end, decimal_mark)}"
        cues.append(f"{timing}\n{segment['text'].strip()}")
    return cues


def to_text(data: Mapping[str, Any]) -> str:
    """The transcript as one block of plain text."""
    return data.get("transcript", "")


def _player_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def to_timed_text(data: Mapping[str, Any]) -> str:
    """One ``[m:ss] text`` line per caption (``[h:mm:ss]`` past an hour). Needs ``segments``.

    Easy for people and AI models to read and cite.
    """
    return "\n".join(f"[{_player_time(float(s['start']))}] {s['text'].strip()}" for s in _segments(data))


def to_json(data: Mapping[str, Any], **json_kwargs: Any) -> str:
    """The full result (metadata, transcript and any segments) as a JSON string."""
    json_kwargs.setdefault("ensure_ascii", False)
    json_kwargs.setdefault("indent", 2)
    return json.dumps(data, **json_kwargs)


def to_srt(data: Mapping[str, Any]) -> str:
    """SubRip (.srt) subtitles. Needs ``segments`` (``timestamps=True``)."""
    cues = _cues(data, ",")
    return "\n\n".join(f"{index}\n{cue}" for index, cue in enumerate(cues, start=1)) + "\n"


def to_vtt(data: Mapping[str, Any]) -> str:
    """WebVTT (.vtt) subtitles. Needs ``segments`` (``timestamps=True``)."""
    cues = [_escape_vtt_text(cue) for cue in _cues(data, ".")]
    return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"


def _escape_vtt_text(cue: str) -> str:
    # "-->" inside cue text would be read as a timing line, so escape it.
    timing, _, text = cue.partition("\n")
    return f"{timing}\n{text.replace('-->', '--&gt;')}"


_FORMATTERS: Dict[str, Callable[[Mapping[str, Any]], str]] = {
    "text": to_text,
    "timed": to_timed_text,
    "json": to_json,
    "srt": to_srt,
    "vtt": to_vtt,
}


def format_transcript(data: Mapping[str, Any], fmt: str) -> str:
    """Format a transcript as ``"text"``, ``"timed"``, ``"json"``, ``"srt"`` or ``"vtt"``."""
    try:
        formatter = _FORMATTERS[fmt]
    except KeyError:
        raise ValueError(f"Unknown format {fmt!r}. Choose one of: {', '.join(FORMATS)}.") from None
    return formatter(data)
