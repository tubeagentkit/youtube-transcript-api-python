# YouTube Transcript API: Python SDK

[![License](https://img.shields.io/badge/License-MIT-4CAF50?style=for-the-badge)](./LICENSE)
[![Website](https://img.shields.io/badge/Website-getyoutubetranscript.com-FF3B00?style=for-the-badge)](https://getyoutubetranscript.com)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)

The official Python SDK (`getyoutubetranscript`) for the [GetYouTubeTranscript](https://getyoutubetranscript.com) YouTube Transcript API. Get YouTube video transcripts, captions and subtitles (optionally with per-line timestamps) in Python without a Google API key, yt-dlp, or a headless browser. Get YouTube transcripts, search videos and channels, resolve channel handles, browse a channel's full upload history, search inside a channel, pull playlist contents, and check your credit balance, all with one typed client.

Export transcripts as plain text, timed text, JSON, SRT or WebVTT, from Python or the `getyoutubetranscript` command line. Getting `RequestBlocked` or `IpBlocked` from `youtube-transcript-api` on a cloud server? See [below](#getting-requestblocked-or-ipblocked).

[![PyPI](https://img.shields.io/pypi/v/getyoutubetranscript)](https://pypi.org/project/getyoutubetranscript/)

## Install

```bash
pip install getyoutubetranscript
```

Requires Python 3.9+.

## Quickstart

```python
from getyoutubetranscript import Client

client = Client(api_key="sk_live_...")

transcript = client.get_transcript("https://www.youtube.com/watch?v=jNQXAC9IVRw")
print(transcript["title"], transcript["word_count"])
print(transcript["transcript"])
```

## Getting an API key

Every request needs an API key. There are two ways to get one:

1. **Dashboard** - sign up at [getyoutubetranscript.com](https://getyoutubetranscript.com). Free tier: 100 credits, no card required.
2. **Self-serve, in code** - use the `signup`/`verify_signup` helpers below. No key required for either call.

```python
from getyoutubetranscript import signup, verify_signup

signup("you@example.com")          # sends a 6-digit code, valid 10 minutes
# ... read the code from your inbox ...
api_key = verify_signup("you@example.com", "123456")  # -> "sk_live_..."
```

The raw key is returned once by `verify_signup` and can't be retrieved again - store it yourself (env var, secret manager, etc).

## Usage

Every method costs 1 credit unless noted "free" below. Failed and rate-limited requests are never charged. All methods raise `GetYouTubeTranscriptError` on failure - see [Error handling](#error-handling).

### Transcripts

```python
client.get_transcript("jNQXAC9IVRw", language="en")
```

Pass `timestamps=True` to also get one entry per caption line in `segments` (same 1 credit). Without it, the response has no `segments` key.

```python
result = client.get_transcript("5e37ZT3SQbk", timestamps=True)
print(result["segments"][0])
# {"start": 3.96, "duration": 4.56, "text": "So, Reed, education, which a lot of"}
```

Each segment is `{"start", "duration", "text"}` with `start` and `duration` in seconds. The `Segment` and `TranscriptData` typed dicts are importable from `getyoutubetranscript`.

### Formats: text, timed text, JSON, SRT, WebVTT

Turn a transcript into a file format with the formatters. Timed text, SRT and WebVTT need per-line timing, so fetch with `timestamps=True` (same 1 credit).

```python
from getyoutubetranscript import Client, to_srt, to_vtt, to_timed_text, to_json, to_text

result = client.get_transcript("5e37ZT3SQbk", timestamps=True)

open("video.srt", "w", encoding="utf-8").write(to_srt(result))   # SubRip subtitles
open("video.vtt", "w", encoding="utf-8").write(to_vtt(result))   # WebVTT subtitles
print(to_timed_text(result))  # "[0:03] So, Reed, education, ..." one line per caption
print(to_json(result))        # metadata, transcript and segments
print(to_text(result))        # one block of plain text
```

`format_transcript(result, "srt")` does the same with the format as a string (`"text"`, `"timed"`, `"json"`, `"srt"`, `"vtt"`).

### Search

```python
first_page = client.search("lofi beats", type="video", limit=10)

# Pagination: pass continuation_token back as page_token
if first_page.get("continuation_token"):
    page2 = client.search(page_token=first_page["continuation_token"])
```

### Channels

```python
client.resolve_channel("@mkbhd")            # free - handle/URL -> channel ID
client.get_channel_latest("@mkbhd")         # free - metadata + latest uploads
client.search_channel("@mkbhd", "iphone")   # search within a channel
client.list_channel_videos("@mkbhd")        # full paginated upload history

# Pagination (search_channel and list_channel_videos both work the same way)
page = client.list_channel_videos("@mkbhd")
while page["has_more"]:
    page = client.list_channel_videos(continuation=page["continuation_token"])
```

### Playlists

```python
page = client.get_playlist("PLillGF-RfqbYE6Ik_EuXA2iZFcE082B3s")
while page["has_more"]:
    page = client.get_playlist(continuation=page["continuation_token"])
```

### Account

```python
client.get_credits()  # free - plan_credits_left, topup_credits_left, plan, rate_limit_per_minute
```

## Command line

Installing the package also installs a `getyoutubetranscript` command.

```bash
export GETYOUTUBETRANSCRIPT_API_KEY=sk_live_...

getyoutubetranscript https://youtu.be/5e37ZT3SQbk                 # plain text
getyoutubetranscript 5e37ZT3SQbk --format srt > video.srt          # SRT subtitles
getyoutubetranscript 5e37ZT3SQbk --format timed --language en      # [m:ss] lines
getyoutubetranscript VIDEO_1 VIDEO_2 --format json                 # one JSON list
getyoutubetranscript VIDEO_1 VIDEO_2 --format vtt --output-dir subs # subs/<video_id>.vtt
```

Formats: `text` (default), `timed`, `json`, `srt`, `vtt`. Videos can be URLs or IDs. If one video fails, the rest still run and the command exits with status 1. `python -m getyoutubetranscript` works too.

## Error handling

Every non-2xx or `{"success": false}` response raises `GetYouTubeTranscriptError` with the API's parsed error shape:

```python
from getyoutubetranscript import Client, GetYouTubeTranscriptError

client = Client(api_key="sk_live_...")

try:
    client.get_transcript("no-captions-here")
except GetYouTubeTranscriptError as e:
    print(e.code)          # e.g. "NOT_FOUND"
    print(e.message)       # human-readable message from the API
    print(e.status_code)   # 400 / 401 / 402 / 404 / 429 / 503, or 0 for a local network failure
    print(e.response_body) # full parsed error body, e.g. {"creditsLeft": 0} on PAYMENT_REQUIRED
```

## Getting RequestBlocked or IpBlocked?

If you use the open source `youtube-transcript-api` library, you have probably seen `RequestBlocked` or `IpBlocked` once your code runs on a server. YouTube blocks most IP addresses that belong to cloud providers (AWS, Google Cloud, Azure and others), and can also block a home IP that makes many requests. That library's own docs recommend rotating residential proxies as the workaround.

This SDK calls the GetYouTubeTranscript API instead of YouTube, so YouTube never sees your server's IP. There are no proxies to buy, rotate or debug, and the same code works on your laptop, a VPS, a serverless function or a CI job:

```python
from getyoutubetranscript import Client

client = Client(api_key="sk_live_...")
result = client.get_transcript("https://www.youtube.com/watch?v=jNQXAC9IVRw", timestamps=True)
```

The trade-off: it is a paid API with a free tier (each request uses credits), while `youtube-transcript-api` is free to run if you handle the blocking yourself.

## Coming from youtube-transcript-api

The segment shape is the same (`text`, `start`, `duration`, in seconds), so most code ports directly.

| youtube-transcript-api | getyoutubetranscript |
| --- | --- |
| `YouTubeTranscriptApi().fetch(video_id)` | `client.get_transcript(video, timestamps=True)` |
| `fetched.to_raw_data()` | `result["segments"]` (already a list of dicts) |
| `fetch(video_id, languages=["de"])` | `get_transcript(video, language="de")` |
| Video ID only | Video ID or any YouTube URL (watch, youtu.be, Shorts, live) |
| `SRTFormatter()`, `WebVTTFormatter()`, `TextFormatter()`, `JSONFormatter()` | `to_srt`, `to_vtt`, `to_text`, `to_json` |
| CLI: `youtube_transcript_api VIDEO_ID --format json` | CLI: `getyoutubetranscript VIDEO --format json` |
| Proxies for cloud servers | Not needed |

```python
# before
from youtube_transcript_api import YouTubeTranscriptApi
segments = YouTubeTranscriptApi().fetch("jNQXAC9IVRw").to_raw_data()

# after
from getyoutubetranscript import Client
segments = Client(api_key="sk_live_...").get_transcript("jNQXAC9IVRw", timestamps=True)["segments"]
```

Not covered here: a list of preferred fallback languages, listing every available caption track, YouTube's machine translation of captions, and `preserve_formatting`. Request one language at a time with `language=`.

The response also includes the video title, channel name, channel URL, thumbnail and word count, which `youtube-transcript-api` does not return.

## Development

```bash
pip install -e ".[dev]"

# Unit tests - mocked HTTP, no network or API key needed, always safe to run
pytest tests -v --ignore=tests/live

# Live integration tests - hits the real API, spends credits, needs a key
GYT_API_KEY=sk_live_... pytest tests/live -v
```

## Links

- [Full API docs](https://getyoutubetranscript.com/docs)
- [OpenAPI spec](https://getyoutubetranscript.com/openapi.json)
- [MCP server](https://getyoutubetranscript.com/youtube-mcp-server) - if you want an AI agent to call this API directly instead of via Python

## Related projects

Other ways to use the [GetYouTubeTranscript API](https://getyoutubetranscript.com):

- [youtube-transcript-api](https://github.com/tubeagentkit/youtube-transcript-api): YouTube Transcript API docs, endpoint reference, OpenAPI spec and examples in curl, Python, JavaScript, Go and PHP
- [youtube-transcript-api-node](https://github.com/tubeagentkit/youtube-transcript-api-node): YouTube Transcript API SDK for Node.js / TypeScript
- [youtube-mcp](https://github.com/tubeagentkit/youtube-mcp): Remote YouTube MCP server for Claude, ChatGPT, Cursor and VS Code
- [youtube-transcript-skills](https://github.com/tubeagentkit/youtube-transcript-skills): YouTube transcript Agent Skill for Claude Code, Cursor, Codex and OpenClaw
- [youtube-transcript-cursor-plugin](https://github.com/tubeagentkit/youtube-transcript-cursor-plugin): YouTube Transcript Cursor plugin bundling the MCP server, skills, commands and a research agent
- [n8n-nodes-getyoutubetranscript](https://github.com/tubeagentkit/n8n-nodes-getyoutubetranscript): YouTube transcript n8n community node, also usable as an AI Agent tool

## License

MIT - see [LICENSE](./LICENSE).
