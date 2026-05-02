"""Backend type and model size enums with CLI/config compatibility."""

from __future__ import annotations

from enum import Enum, StrEnum
from typing import Any, Self


class BackendType(StrEnum):
    """Valid backend types for audio transcription.

    Inherits from str and Enum for JSON serialization support.
    """

    OPENAI = "openai"
    FASTER_WHISPER = "faster_whisper"
    AUTO = "auto"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a string to BackendType case-insensitively.

        Args:
            value: String to parse (e.g., "OpenAI", "openai", "OPENAI")

        Returns:
            BackendType enum member

        Raises:
            ValueError: If value is not a valid backend type
        """
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid backend type '{value}'. Valid options: {valid_options}"
            ) from None


class ModelSize(StrEnum):
    """Valid model sizes for transcription models.

    Inherits from str and Enum for JSON serialization support.

    Available models:
        - tiny: Fastest, lowest quality (~75MB)
        - base: Fast, good quality (~150MB)
        - small: Balanced (~500MB)
        - medium: Better quality (~1.5GB)
        - large: Best quality (~3GB, same as large-v3)
        - large-v3: Latest large model (~3GB)
        - large-v3-turbo: Fast large model (~3GB, faster inference)
    """

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    LARGE_V3 = "large-v3"
    LARGE_V3_TURBO = "large-v3-turbo"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a string to ModelSize case-insensitively.

        Args:
            value: String to parse (e.g., "Large", "large", "LARGE")

        Returns:
            ModelSize enum member

        Raises:
            ValueError: If value is not a valid model size
        """
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        # Handle aliases: "large" is a distinct model size, not an alias
        # Users who want large-v3 should specify "large-v3" explicitly
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid model size '{value}'. Valid options: {valid_options}"
            ) from None


def to_json_serializable(obj: Any) -> str:
    """Convert enum to JSON serializable string.

    Args:
        obj: Enum or string to convert

    Returns:
        String value for JSON serialization
    """
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)
