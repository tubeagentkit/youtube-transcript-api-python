"""Python SDK for the GetYouTubeTranscript REST API.

    from getyoutubetranscript import Client

    client = Client(api_key="sk_live_...")
    transcript = client.get_transcript("https://www.youtube.com/watch?v=jNQXAC9IVRw")

See https://getyoutubetranscript.com/docs for the full API reference.
"""

from .client import Client, signup, verify_signup
from .exceptions import GetYouTubeTranscriptError
from .formatters import format_transcript, to_json, to_srt, to_text, to_timed_text, to_vtt
from .types import Segment, TranscriptData

__version__ = "0.3.1"

__all__ = [
    "Client",
    "GetYouTubeTranscriptError",
    "Segment",
    "TranscriptData",
    "format_transcript",
    "signup",
    "to_json",
    "to_srt",
    "to_text",
    "to_timed_text",
    "to_vtt",
    "verify_signup",
    "__version__",
]
