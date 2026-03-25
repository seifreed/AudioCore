"""Output formatters for transcription results.

This module provides formatters for converting TranscriptionResult
to various output formats:
- text: Plain text with timestamps [HH:MM:SS.mmm]
- json: Structured JSON with full metadata
- srt: SRT subtitle format for video players
- vtt: WebVTT subtitle format for web players
"""

from audiocore.output.json import format_json
from audiocore.output.srt import format_srt
from audiocore.output.text import format_text
from audiocore.output.vtt import format_vtt

__all__ = ["format_text", "format_json", "format_srt", "format_vtt"]
