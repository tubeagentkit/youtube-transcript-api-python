"""Response types for the GetYouTubeTranscript API.

These are ``TypedDict`` hints only: the client still returns plain dicts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


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
    caption_type: Optional[Literal["manual", "auto", "ai"]]  # creator captions, speech recognition, or AI; None = unknown
    fetched_at: Optional[str]  # ISO 8601 time the transcript was fetched from YouTube
    segments: List[Segment]  # present only when timestamps=True
    source: Literal["ai"]  # present only on AI transcripts
    duration_seconds: int  # video length; present only on AI transcripts, the cost is based on it


class TranscriptData(_TranscriptFields, total=False):
    """Result of :meth:`Client.get_transcript`."""

    cached: bool  # True when served from the stored copy rather than fetched now; absent on AI transcripts


TranscriptMode = Literal["native", "auto", "generate"]
"""``native``: captions only (1 credit). ``auto``: captions if any, else AI. ``generate``: always AI.
An AI transcript costs 3 credits per minute of video, rounded up, minimum 3."""


class _JobError(TypedDict, total=False):
    code: str
    message: str


class _TranscriptJobRequired(TypedDict):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    video_id: str
    credits_charged: int  # taken when the job started; refunded automatically if it fails
    poll_url: str  # /api/v1/transcript/jobs?id=<job_id>
    poll_interval_seconds: int  # how long to wait between polls (5)
    created_at: str


class TranscriptJob(_TranscriptJobRequired, total=False):
    """An AI transcript job, returned when the transcript takes longer than about 20 seconds."""

    error: _JobError  # present only when status is "failed"


class _TranscriptResultRequired(TypedDict):
    data: Optional[TranscriptData]  # None while an AI transcript is still being made
    credits_charged: Optional[int]  # X-Credits-Charged header; None when not sent


class TranscriptResult(_TranscriptResultRequired, total=False):
    """Result of :meth:`Client.start_transcript`."""

    job: TranscriptJob  # present on a 202 answer


class TranscriptJobResult(TypedDict):
    """Result of :meth:`Client.get_transcript_job`."""

    data: Optional[TranscriptData]  # None while the job is queued or running
    job: TranscriptJob


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


ChannelTab = Literal["videos", "shorts", "streams"]  # streams = the channel's Live tab
ChannelSort = Literal["latest", "popular", "oldest"]


class _PageFields(TypedDict, total=False):
    has_more: bool
    continuation_token: Optional[str]  # None on the last page; expires after 24 hours


class ChannelPlaylist(TypedDict, total=False):
    position: int
    id: str
    title: str
    link: str
    type: str
    video_count_text: str  # as shown on YouTube, e.g. "12 videos"
    video_count: int
    thumbnail: str


class ChannelPlaylistsPage(_PageFields, total=False):
    """Result of :meth:`Client.list_channel_playlists`."""

    playlists: List[ChannelPlaylist]


class ChannelPost(TypedDict, total=False):
    position: int
    id: str
    url: str
    text: str
    links: List[str]
    published_time: str  # relative, as shown on YouTube, e.g. "2 years ago"
    likes: str  # as shown on YouTube, e.g. "12K"
    comments: str
    attachment: Dict[str, Any]  # the post's image, video or poll, when it has one


class ChannelPostsPage(_PageFields, total=False):
    """Result of :meth:`Client.list_channel_posts`."""

    posts: List[ChannelPost]


class BannerSize(TypedDict, total=False):
    url: str
    width: int
    height: int


class ChannelBannerImages(TypedDict, total=False):
    original: str  # uncropped
    largest: str
    sizes: List[BannerSize]


class ChannelBanner(TypedDict, total=False):
    """Result of :meth:`Client.get_channel_banner`."""

    channel_id: str
    handle: str
    title: str
    avatar: str
    has_banner: bool
    banner: ChannelBannerImages  # present only when has_banner is True


class RelatedVideoChannel(TypedDict, total=False):
    name: str
    id: str


class RelatedVideo(TypedDict, total=False):
    position: int
    id: str
    title: str
    link: str
    channel: RelatedVideoChannel
    views: str  # as shown on YouTube
    published_time: str
    length: str  # e.g. "3:32"
    thumbnail: str


class RelatedVideosData(TypedDict, total=False):
    """Result of :meth:`Client.get_related_videos`."""

    video_id: str
    related: List[RelatedVideo]


class VideoDislikesData(TypedDict, total=False):
    """Result of :meth:`Client.get_video_dislikes`. Every number is an estimate."""

    video_id: str
    likes: int
    dislikes: int
    rating: float  # out of 5
    view_count: int
    raw_likes: int
    raw_dislikes: int
    deleted: bool
    estimated: bool  # always True
    source: str


class VideoDetailsChannel(TypedDict, total=False):
    id: str
    name: str
    subscribers: str  # rounded label as shown on YouTube, e.g. "4.56M subscribers"
    thumbnail: str


class VideoThumbnail(TypedDict, total=False):
    url: str
    width: int
    height: int


class VideoDetails(TypedDict, total=False):
    """Result of :meth:`Client.get_video_details`."""

    video_id: str
    title: str
    description: str
    channel: VideoDetailsChannel
    views: str  # exact view count as a digit string, e.g. "1840125263"
    likes: str  # rounded label as shown on YouTube, e.g. "19M"
    upload_date: str  # as shown on YouTube, e.g. "Oct 24, 2009"
    duration: int  # length in seconds
    duration_formatted: str  # e.g. "3:33"
    thumbnails: List[VideoThumbnail]
    is_live: bool
    is_private: bool
    keywords: List[str]  # the video's tags


class VideoCommentChannel(TypedDict, total=False):
    """The commenter."""

    id: str
    handle: str
    link: str
    thumbnail: str


class VideoComment(TypedDict, total=False):
    comment_id: str
    link: str
    channel: VideoCommentChannel
    published_date: str  # relative, as shown on YouTube, e.g. "7 years ago (edited)"
    text: str
    likes: str  # rounded label, e.g. "73K"
    replies: int


class VideoCommentsPage(_PageFields, total=False):
    """Result of :meth:`Client.get_video_comments`."""

    video_id: str
    comments: List[VideoComment]


class TikTokSegment(TypedDict):
    """One caption line of a TikTok transcript (no ``duration``, unlike :class:`Segment`)."""

    start: float  # start time in seconds
    text: str


class TikTokTranscript(TypedDict, total=False):
    """Result of :meth:`Client.get_tiktok_transcript`."""

    video_id: str  # numeric TikTok video ID, e.g. "7039900146041343278"
    author: str  # the creator's handle, without the "@"
    description: str  # the video's caption, cut to 500 characters
    language: str  # caption language, e.g. "eng-US"
    auto_generated: bool
    segments: List[TikTokSegment]
