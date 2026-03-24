"""Media processing module for AudioCore.

This module provides utilities for probing and analyzing media files,
and extracting audio to normalized WAV format.
"""

from audiocore.media.extractor import extract_audio, temp_audio_file
from audiocore.media.probe import probe

__all__ = [
    "extract_audio",
    "probe",
    "temp_audio_file",
]
