"""Output format enum for transcription results."""

from enum import StrEnum


class OutputFormat(StrEnum):
    """Valid output formats for transcription results.

    Inherits from str and Enum for JSON serialization support.
    """

    TEXT = "text"
    JSON = "json"
    SRT = "srt"
    VTT = "vtt"

    @classmethod
    def parse(cls, value: str) -> OutputFormat:
        """Parse a string to OutputFormat case-insensitively.

        Supports both format name and file extension:
        - "text", "txt" -> OutputFormat.TEXT
        - "json" -> OutputFormat.JSON
        - "srt" -> OutputFormat.SRT
        - "vtt" -> OutputFormat.VTT

        Args:
            value: String to parse (e.g., "SRT", "srt", ".srt")

        Returns:
            OutputFormat enum member

        Raises:
            ValueError: If value is not a valid output format
        """
        normalized = value.lower().strip().lstrip(".")

        # Map common extensions to format names
        extension_map = {
            "txt": "text",
            "text": "text",
            "json": "json",
            "srt": "srt",
            "vtt": "vtt",
        }

        format_name = extension_map.get(normalized, normalized)
        try:
            return cls(format_name)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid output format '{value}'. Valid options: {valid_options}"
            ) from None
