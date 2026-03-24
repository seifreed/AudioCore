"""
Input-related exceptions.

These exceptions are raised when there are problems with input files
or media formats.
"""

from typing import Any

from audiocore.errors.base import AudioCoreError


class InputError(AudioCoreError):
    """
    Base exception for input-related errors.

    Inherit from this for exceptions related to user input,
    file paths, and media formats.
    """

    error_code: str = "AUD-001"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Add default suggestions if none provided
        if suggestions is None:
            suggestions = [
                "Check input file path",
                "Verify file exists and is readable",
                "Ensure file format is supported",
            ]
        super().__init__(message, context, suggestions, cause)


class InvalidInputError(InputError):
    """
    Exception raised when input validation fails.

    This includes:
    - File not found
    - Invalid file path
    - Unsupported input type

    Example:
        >>> raise InvalidInputError(
        ...     "File not found",
        ...     context={"file_path": "/path/to/audio.mp3"},
        ...     suggestions=["Check file path exists", "Verify file permissions"]
        ... )
    """

    error_code: str = "AUD-002"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Add default suggestions if none provided
        if suggestions is None:
            suggestions = [
                "Check file path exists",
                "Verify file permissions",
                "Ensure file is readable",
            ]
        super().__init__(message, context, suggestions, cause)


class MediaFormatError(InputError):
    """
    Exception raised when media format is unsupported or invalid.

    This is raised when:
    - Media file format is not supported
    - File is corrupted
    - Codec is not available

    Example:
        >>> raise MediaFormatError(
        ...     "Unsupported media format",
        ...     context={
        ...         "file_path": "video.mkv",
        ...         "format": "matroska",
        ...     },
        ...     suggestions=[
        ...         "Convert to supported format (mp3, wav, mp4)",
        ...         "Install additional codecs",
        ...     ]
        ... )
    """

    error_code: str = "AUD-003"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Add default suggestions if none provided
        if suggestions is None:
            suggestions = [
                "Convert to supported format (mp3, wav, mp4)",
                "Check file is not corrupted",
                "Verify codec availability",
            ]
        super().__init__(message, context, suggestions, cause)
