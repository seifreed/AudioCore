"""Output formatters for transcription results.

This module provides formatters for converting TranscriptionResult
to various output formats:
- text: Plain text with timestamps [HH:MM:SS.mmm]
- json: Structured JSON with full metadata
- srt: SRT subtitle format for video players
- vtt: WebVTT subtitle format for web players

Also provides file writing utilities:
- write_output: Write content to file with atomic write and directory creation
- format_and_write: Format result and write to file with auto-format detection
"""

from audiocore.output.file_writer import (
    OutputFileConfig,
    format_and_write,
    write_output,
)
from audiocore.output.json import format_json
from audiocore.output.srt import format_srt
from audiocore.output.text import format_text
from audiocore.output.vtt import format_vtt

__all__ = [
    # Formatters
    "format_text",
    "format_json",
    "format_srt",
    "format_vtt",
    # File writing
    "write_output",
    "format_and_write",
    "OutputFileConfig",
]
