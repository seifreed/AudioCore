"""Transcription request options and result models."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class TranscriptionOptions(BaseModel):
    """Configuration options for transcription requests.

    Provides sensible defaults for all parameters while allowing
    customization for specific use cases.

    Attributes:
        language: Optional ISO 639-1 language code (e.g., "en", "es").
        model_size: Model size to use, defaults to BASE.
        backend: Backend to use, defaults to AUTO for automatic selection.
        output_format: Output format, defaults to TEXT.
        backend_preference: Selection policy for automatic backend selection.
        strict_vad: If True, raise VADError when VAD fails. If False (default),
            fall back to whole-file transcription when VAD fails.

    Example:
        >>> opts = TranscriptionOptions()
        >>> opts.backend
        <BackendType.AUTO: 'auto'>
        >>> opts.model_size
        <ModelSize.BASE: 'base'>
        >>> opts.output_format
        <OutputFormat.TEXT: 'text'>
    """

    model_config = {"strict": True, "extra": "forbid"}

    language: str | None = Field(
        default=None, description="ISO 639-1 language code (e.g., 'en', 'es', 'fr')"
    )
    model_size: ModelSize = Field(
        default=ModelSize.BASE,
        description="Model size for transcription (tiny, base, small, medium, large)",
    )
    backend: BackendType = Field(
        default=BackendType.AUTO,
        description="Backend to use (openai, faster_whisper, or auto)",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT, description="Output format (text, srt, vtt, json)"
    )
    backend_preference: SelectionPolicy = Field(
        default=SelectionPolicy.AUTO,
        description="Policy for automatic backend selection (prefer_local, prefer_cloud, auto)",
    )
    strict_vad: bool = Field(
        default=False,
        description="If True, raise VADError when VAD fails. If False, fall back to whole-file transcription.",
    )


class TranscriptionResult(BaseModel):
    """Complete transcription result with segments and metadata.

    Contains the full transcription output including time-segmented
    text, source media information, and the configuration used.

    Attributes:
        segments: List of time-segmented transcriptions.
        media_info: Metadata about the source media (includes media duration).
        config_used: Configuration options used for this transcription.
        processing_time_seconds: Duration of the transcription process in seconds.
            (Note: This is processing time, not media duration. For media duration,
            use media_info.duration)
        backend_used: Backend that performed this transcription.
        formatted_output: Formatted transcription output (text or JSON).
        failed_segments: List of segments that failed transcription (if partial failure).

    Example:
        >>> from audiocore.models import Segment, MediaInfo, TranscriptionOptions
        >>> result = TranscriptionResult(
        ...     segments=[Segment(start_time=0.0, end_time=5.0, text='Hello')],
        ...     media_info=MediaInfo(duration=120.0, format='mp4'),
        ...     config_used=TranscriptionOptions(),
        ...     processing_time_seconds=15.5,
        ...     backend_used=BackendType.OPENAI
        ... )
        >>> result.segments[0].text
        'Hello'
        >>> result.media_info.duration  # Media duration
        120.0
        >>> result.processing_time_seconds  # Processing time
        15.5
    """

    model_config = {"strict": True, "extra": "forbid"}

    segments: Annotated[
        list[Segment], Field(min_length=0, description="List of transcription segments")
    ]
    media_info: MediaInfo = Field(description="Metadata about the source media")
    config_used: TranscriptionOptions = Field(
        description="Configuration options used for this transcription"
    )
    processing_time_seconds: float = Field(
        ge=0,
        description="Time taken to process the transcription in seconds (not media duration)",
    )
    backend_used: BackendType = Field(
        description="Backend that performed this transcription"
    )
    formatted_output: str | None = Field(
        default=None,
        description="Formatted transcription output (text or JSON based on output_format)",
    )
    failed_segments: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Segments that failed transcription (start_time, end_time, error)",
    )
