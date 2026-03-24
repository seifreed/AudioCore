"""MediaInfo model for audio/video metadata."""

from typing import Optional

from pydantic import BaseModel, Field


class MediaInfo(BaseModel):
    """Audio/video metadata for transcription context.

    Stores information about the source media file that was transcribed,
    including duration, format, and technical properties.

    Attributes:
        duration: Total duration in seconds (must be > 0).
        format: Media container format (e.g., "mp4", "mp3", "wav").
        codec: Audio codec used (optional, e.g., "aac", "mp3", "pcm").
        sample_rate: Audio sample rate in Hz (optional, must be > 0 if provided).
        channels: Number of audio channels (optional, must be > 0 if provided).

    Example:
        >>> info = MediaInfo(duration=120.5, format="mp4")
        >>> info.duration
        120.5
        >>> info.sample_rate is None
        True
        >>> info.model_dump()
        {'duration': 120.5, 'format': 'mp4', 'codec': None, 'sample_rate': None, 'channels': None}
    """

    model_config = {"strict": True, "extra": "forbid"}

    duration: float = Field(gt=0, description="Total duration of the media in seconds")
    format: str = Field(description="Media container format (e.g., 'mp4', 'mp3', 'wav')")
    codec: Optional[str] = Field(
        default=None, description="Audio codec used (e.g., 'aac', 'mp3', 'pcm')"
    )
    sample_rate: Optional[int] = Field(default=None, gt=0, description="Audio sample rate in Hz")
    channels: Optional[int] = Field(default=None, gt=0, description="Number of audio channels")
