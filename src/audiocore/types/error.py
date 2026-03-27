"""Error classification enum for model and processing errors."""

from __future__ import annotations

from enum import StrEnum
from typing import Self


class ModelErrorType(StrEnum):
    """Classification of errors that can occur during transcription.

    Inherits from str and Enum for JSON serialization support.
    Grouped by error category for programmatic handling.
    """

    # Input errors - file and format issues
    FILE_NOT_FOUND = "file_not_found"
    INVALID_FORMAT = "invalid_format"
    EXTRACTION_FAILED = "extraction_failed"

    # VAD errors - voice activity detection issues
    VAD_FAILED = "vad_failed"
    VAD_MODEL_LOAD_FAILED = "vad_model_load_failed"

    # Backend errors - transcription backend issues
    BACKEND_UNAVAILABLE = "backend_unavailable"
    TRANSCRIPTION_FAILED = "transcription_failed"

    # API errors - cloud API specific issues
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    API_TIMEOUT = "api_timeout"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a string to ModelErrorType case-insensitively.

        Args:
            value: String to parse (e.g., "FILE_NOT_FOUND", "file_not_found", "file-not-found")

        Returns:
            ModelErrorType enum member

        Raises:
            ValueError: If value is not a valid error type
        """
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid error type '{value}'. Valid options: {valid_options}"
            ) from None

    def is_input_error(self) -> bool:
        """Check if this is an input-related error."""
        return self in (
            ModelErrorType.FILE_NOT_FOUND,
            ModelErrorType.INVALID_FORMAT,
            ModelErrorType.EXTRACTION_FAILED,
        )

    def is_vad_error(self) -> bool:
        """Check if this is a VAD-related error."""
        return self in (
            ModelErrorType.VAD_FAILED,
            ModelErrorType.VAD_MODEL_LOAD_FAILED,
        )

    def is_backend_error(self) -> bool:
        """Check if this is a backend-related error."""
        return self in (
            ModelErrorType.BACKEND_UNAVAILABLE,
            ModelErrorType.TRANSCRIPTION_FAILED,
        )

    def is_api_error(self) -> bool:
        """Check if this is an API-related error."""
        return self in (
            ModelErrorType.AUTH_FAILED,
            ModelErrorType.RATE_LIMITED,
            ModelErrorType.API_TIMEOUT,
        )
