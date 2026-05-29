"""Transcription request options and result models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Self

from pydantic import BaseModel, Field, model_validator

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.types import (
    BackendType,
    ModelSize,
    OutputFormat,
    SelectionPolicy,
    TranscriptionTask,
)

if TYPE_CHECKING:
    from audiocore.config import AppConfig


class FailedSegment(BaseModel):
    """A segment that failed during transcription.

    Attributes:
        start_time: Start time of the failed segment in seconds.
        end_time: End time of the failed segment in seconds.
        error: Error message describing the failure.
    """

    model_config = {"strict": True, "extra": "forbid"}

    start_time: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="Start time of the failed segment",
    )
    end_time: float = Field(
        ge=0,
        allow_inf_nan=False,
        description="End time of the failed segment",
    )
    error: str = Field(description="Error message describing the failure")

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        """Validate that failed segment times are ordered."""
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be >= start_time ({self.start_time})"
            )
        return self


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
        word_timestamps: If True, request word-level timestamps from the backend
            and attach them to each segment's ``words`` field. Defaults to False.
        task: Whether to transcribe (keep the source language) or translate the
            audio to English. Defaults to TranscriptionTask.TRANSCRIBE.

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
    word_timestamps: bool = Field(
        default=False,
        description="If True, request word-level timestamps from the backend and attach them to segments.",
    )
    task: TranscriptionTask = Field(
        default=TranscriptionTask.TRANSCRIBE,
        description="Task to perform: transcribe (keep source language) or translate (to English).",
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
        allow_inf_nan=False,
        description="Time taken to process the transcription in seconds (not media duration)",
    )
    backend_used: BackendType = Field(description="Backend that performed this transcription")
    formatted_output: str | None = Field(
        default=None,
        description="Formatted transcription output (text or JSON based on output_format)",
    )
    failed_segments: list[FailedSegment] = Field(
        default_factory=list,
        description="Segments that failed transcription (start_time, end_time, error)",
    )


def transcription_options_from_config(
    config: AppConfig,
    *,
    backend: BackendType | None = None,
    model_size: ModelSize | None = None,
    language: str | None = None,
    output_format: OutputFormat | None = None,
    backend_preference: SelectionPolicy | None = None,
) -> TranscriptionOptions:
    """Build transcription options from AppConfig without inventing model overrides.

    ``TranscriptionOptions`` tracks which fields were explicitly provided.
    FasterWhisperBackend uses that to distinguish a caller's model override
    from its own backend-specific ``faster_whisper.model_size`` config. Passing
    the top-level default model as an explicit option would accidentally mask
    the backend-specific model setting.
    """
    option_values: dict[str, object] = {
        "backend": backend if backend is not None else config.backend,
        "language": language if language is not None else config.language,
        "output_format": output_format if output_format is not None else config.output_format,
        "backend_preference": (
            backend_preference if backend_preference is not None else config.backend_preference
        ),
    }

    default_model_size = TranscriptionOptions.model_fields["model_size"].default
    if model_size is not None:
        option_values["model_size"] = model_size
    elif config.model != default_model_size:
        option_values["model_size"] = config.model

    return TranscriptionOptions.model_validate(option_values)
