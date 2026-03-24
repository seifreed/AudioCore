"""
Processing-related exceptions.

These exceptions are raised when there are problems during audio
processing, VAD detection, or other processing operations.
"""

from typing import Any

from audiocore.errors.base import AudioCoreError


class ProcessingError(AudioCoreError):
    """
    Base exception for processing-related errors.

    Inherit from this for exceptions related to audio processing,
    voice activity detection, and other pipeline stages.
    """

    error_code: str = "AUD-400"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check input file integrity",
                "Verify processing parameters",
                "Try with different settings",
            ]
        super().__init__(message, context, suggestions, cause)


class VADError(ProcessingError):
    """
    Exception raised when VAD (Voice Activity Detection) fails.

    This includes:
    - Model loading failure
    - VAD processing error
    - Memory exhaustion during VAD

    Example:
        >>> raise VADError(
        ...     "Failed to load Silero VAD model",
        ...     context={
        ...         "model": "silero_vad",
        ...         "reason": "Torch hub unavailable",
        ...     },
        ...     suggestions=[
        ...         "Check internet connection",
        ...         "Use cached model if available",
        ...         "Try fallback whole-file processing",
        ...     ]
        ... )
    """

    error_code: str = "AUD-401"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check VAD model availability",
                "Verify sufficient memory",
                "Try whole-file transcription without VAD",
            ]
        super().__init__(message, context, suggestions, cause)
