"""Response types for the GetYouTubeTranscript API.

These are ``TypedDict`` hints only: the client still returns plain dicts.
"""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict


class Segment(TypedDict):
    """One caption line, returned in ``segments`` when ``timestamps=True``."""

    start: float  # start time in seconds
    duration: float  # duration in seconds
    text: str


class _TranscriptRequired(TypedDict):
    video_id: str
    language_code: str  # the caption track actually returned
    title: str
    author_name: str
    author_url: str
    thumbnail_url: str
    transcript: str
    word_count: int


class _TranscriptFields(_TranscriptRequired, total=False):
    requested_language: str  # differs from language_code when YouTube fell back to another track
    caption_type: Optional[Literal["manual", "auto"]]  # creator captions vs speech recognition; None = unknown
    fetched_at: Optional[str]  # ISO 8601 time the transcript was fetched from YouTube
    segments: List[Segment]  # present only when timestamps=True


class TranscriptData(_TranscriptFields, total=False):
    """Result of :meth:`Client.get_transcript`."""

    cached: bool  # True when served from the stored copy rather than fetched now


class TranscriptLanguage(TypedDict):
    """One caption language a video offers."""

    language_code: str
    name: str  # YouTube's display name, e.g. "English (auto-generated)"
    caption_type: Literal["manual", "auto"]


class TranscriptLanguagesData(TypedDict):
    """Result of :meth:`Client.get_transcript_languages`."""

    video_id: str
    default_language_code: Optional[str]  # what get_transcript returns with no language; None without captions
    languages: List[TranscriptLanguage]  # empty when the video has captions turned off


BatchStatus = Literal["queued", "processing", "completed"]


class BatchItem(_TranscriptFields, total=False):
    """One video in a batch. Succeeded items carry the transcript fields; failed ones an ``error_code``."""

    position: int  # index in the submitted ``videos`` list (after de-duplication)
    status: Literal["pending", "succeeded", "failed"]
    charged: bool  # True when this video used a credit
    error_code: str  # e.g. "TRANSCRIPT_DISABLED", "VIDEO_UNAVAILABLE", "PAYMENT_REQUIRED"


class BatchData(TypedDict, total=False):
    """Result of :meth:`Client.create_batch`, :meth:`Client.get_batch` and :meth:`Client.wait_for_batch`."""

    batch_id: str
    status: BatchStatus
    language: str
    timestamps: bool
    total: int
    succeeded: int
    failed: int
    pending: int
    webhook_status: Literal["none", "pending", "delivered", "failed"]
    created_at: str
    completed_at: Optional[str]
    results_url: str
    webhook_secret: str  # only in the create_batch response, and only when webhook_url was given
    idempotent_replay: bool  # create_batch: True when the Idempotency-Key matched an earlier batch
    credits_charged: int  # get_batch / wait_for_batch
    items: List[BatchItem]  # get_batch: one page; wait_for_batch: every item
    next_offset: Optional[int]  # get_batch: offset of the next page, None on the last one
