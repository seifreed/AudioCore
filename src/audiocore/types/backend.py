"""Backend type and model size enums with CLI/config compatibility."""

from enum import Enum
from typing import Any


class BackendType(str, Enum):
    """Valid backend types for audio transcription.

    Inherits from str and Enum for JSON serialization support.
    """

    OPENAI = "openai"
    FASTER_WHISPER = "faster_whisper"
    AUTO = "auto"

    @classmethod
    def parse(cls, value: str) -> "BackendType":
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
            raise ValueError(f"Invalid backend type '{value}'. Valid options: {valid_options}")


class ModelSize(str, Enum):
    """Valid model sizes for transcription models.

    Inherits from str and Enum for JSON serialization support.
    """

    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

    @classmethod
    def parse(cls, value: str) -> "ModelSize":
        """Parse a string to ModelSize case-insensitively.

        Args:
            value: String to parse (e.g., "Large", "large", "LARGE")

        Returns:
            ModelSize enum member

        Raises:
            ValueError: If value is not a valid model size
        """
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(f"Invalid model size '{value}'. Valid options: {valid_options}")


def to_json_serializable(obj: Any) -> str:
    """Convert enum to JSON serializable string.

    Args:
        obj: Enum or string to convert

    Returns:
        String value for JSON serialization
    """
    if isinstance(obj, str) and isinstance(obj, Enum):
        return obj.value
    return str(obj)
