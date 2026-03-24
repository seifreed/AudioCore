"""Media processing module for AudioCore.

This module provides utilities for probing and analyzing media files,
and extracting audio to normalized WAV format.
"""

from audiocore.media.extractor import extract_audio, temp_audio_file
from audiocore.media.formats import (
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
    is_format_supported,
    validate_format_or_raise,
)
from audiocore.media.probe import probe

__all__ = [
    "SUPPORTED_AUDIO_FORMATS",
    "SUPPORTED_FORMATS",
    "SUPPORTED_VIDEO_FORMATS",
    "extract_audio",
    "is_format_supported",
    "probe",
    "temp_audio_file",
    "validate_format_or_raise",
]
