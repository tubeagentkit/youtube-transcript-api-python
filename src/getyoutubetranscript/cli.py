"""Command line: ``getyoutubetranscript VIDEO [VIDEO ...] [--format srt]``.

Reads the API key from ``--api-key`` or the ``GETYOUTUBETRANSCRIPT_API_KEY``
environment variable.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .client import Client
from .exceptions import GetYouTubeTranscriptError
from .formatters import FORMATS, TIMED_FORMATS, format_transcript, to_json

API_KEY_ENV = "GETYOUTUBETRANSCRIPT_API_KEY"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="getyoutubetranscript",
        description="Get YouTube video transcripts as text, timed text, JSON, SRT or WebVTT.",
    )
    parser.add_argument("videos", nargs="+", metavar="VIDEO", help="YouTube video URL or 11-character video ID")
    parser.add_argument("-f", "--format", choices=FORMATS, default="text", help="output format (default: text)")
    parser.add_argument("-l", "--language", help="caption language code, e.g. en or es")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="write one <video_id>.<format> file per video instead of printing (needed for several videos in a timed, SRT or VTT format)",
    )
    parser.add_argument("--api-key", help=f"API key (default: ${API_KEY_ENV})")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _extension(fmt: str) -> str:
    return "txt" if fmt in ("text", "timed") else fmt


def main(argv: Optional[List[str]] = None, client: Optional[Client] = None) -> int:
    try:
        return _run(argv, client)
    except BrokenPipeError:
        # Output piped into a command that stopped reading (e.g. `| head`): exit quietly.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        return 0


def _run(argv: Optional[List[str]], client: Optional[Client]) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.format in TIMED_FORMATS and len(args.videos) > 1 and not args.output_dir:
        parser.error(f"--output-dir is required to save {args.format} for more than one video")

    if client is None:
        api_key = args.api_key or os.environ.get(API_KEY_ENV)
        if not api_key:
            parser.error(f"no API key: pass --api-key or set {API_KEY_ENV} (get one at https://getyoutubetranscript.com)")
        client = Client(api_key=api_key)

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    json_results = []
    for video in args.videos:
        try:
            data = client.get_transcript(
                video, language=args.language, timestamps=args.format in TIMED_FORMATS or args.format == "json"
            )
        except GetYouTubeTranscriptError as e:
            failures += 1
            print(f"{video}: {e.message} ({e.code})", file=sys.stderr)
            continue

        if args.output_dir:
            path = args.output_dir / f"{data['video_id']}.{_extension(args.format)}"
            path.write_text(format_transcript(data, args.format), encoding="utf-8")
            print(path, file=sys.stderr)
        elif args.format == "json":
            json_results.append(data)
        else:
            print(format_transcript(data, args.format))

    if json_results:
        print(to_json(json_results[0] if len(args.videos) == 1 else json_results))

    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
