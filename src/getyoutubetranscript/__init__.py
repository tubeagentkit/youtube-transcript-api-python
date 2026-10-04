"""Python SDK for the GetYouTubeTranscript REST API.

    from getyoutubetranscript import Client

    client = Client(api_key="sk_live_...")
    transcript = client.get_transcript("https://www.youtube.com/watch?v=jNQXAC9IVRw")

See https://getyoutubetranscript.com/docs for the full API reference.
"""

from .client import Client, signup, verify_signup
from .exceptions import GetYouTubeTranscriptError
from .types import Segment, TranscriptData

__version__ = "0.2.1"

__all__ = [
    "Client",
    "GetYouTubeTranscriptError",
    "Segment",
    "TranscriptData",
    "signup",
    "verify_signup",
    "__version__",
]
