"""Output formatters for transcription results.

This module provides formatters for converting TranscriptionResult
to various output formats (text, JSON, SRT, VTT).
"""

from audiocore.output.json import format_json
from audiocore.output.text import format_text

__all__ = ["format_text", "format_json"]
