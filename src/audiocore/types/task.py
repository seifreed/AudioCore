"""Transcription task enum (transcribe vs. translate)."""

from __future__ import annotations

from enum import StrEnum
from typing import Self


class TranscriptionTask(StrEnum):
    """The decoding task a backend should perform.

    Whisper models support two tasks. ``TRANSCRIBE`` keeps the audio's original
    language; ``TRANSLATE`` translates speech into English (Whisper's translate
    task only ever targets English, regardless of the source language). Both
    backends map this directly: faster-whisper to its ``task`` argument, OpenAI
    to its separate translations endpoint.

    Inherits from str and Enum for JSON serialization support.
    """

    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a string to TranscriptionTask case-insensitively.

        Args:
            value: String to parse (e.g., "TRANSLATE", "translate").

        Returns:
            TranscriptionTask enum member.

        Raises:
            ValueError: If value is not a valid task.
        """
        normalized = value.lower().strip()
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid transcription task '{value}'. Valid options: {valid_options}"
            ) from None
