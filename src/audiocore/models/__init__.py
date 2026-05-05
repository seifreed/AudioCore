"""Domain models for AudioCore transcription engine.

This module provides Pydantic v2 models for:
- Segment: Time-segmented transcription with validation
- MediaInfo: Audio/video metadata
- TranscriptionOptions: Configuration for transcription requests
- TranscriptionResult: Complete transcription output

All models use strict validation for type safety.
"""

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.models.transcription import (
    FailedSegment,
    TranscriptionOptions,
    TranscriptionResult,
    transcription_options_from_config,
)

__all__ = [
    "FailedSegment",
    "Segment",
    "MediaInfo",
    "TranscriptionOptions",
    "TranscriptionResult",
    "transcription_options_from_config",
]
