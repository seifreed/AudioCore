"""
Backend-related exceptions.

These exceptions are raised when there are problems with transcription
backends such as OpenAI Whisper API or faster-whisper.
"""

from typing import Any

from audiocore.errors.base import AudioCoreError


class BackendError(AudioCoreError):
    """
    Base exception for backend-related errors.

    Inherit from this for exceptions related to transcription
    backends, API failures, and backend availability.
    """

    error_code: str = "AUD-200"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check backend service status",
                "Verify network connectivity",
                "Try alternative backend",
            ]
        super().__init__(message, context, suggestions, cause)


class BackendUnavailableError(BackendError):
    """
    Exception raised when a transcription backend is unavailable.

    This is raised when:
    - Backend dependencies are not installed
    - Backend service is down
    - API key is missing for cloud backends

    Example:
        >>> raise BackendUnavailableError(
        ...     "OpenAI backend unavailable",
        ...     context={"backend": "openai", "reason": "API key not configured"},
        ...     suggestions=[
        ...         "Set AUDIOCORE_OPENAI_API_KEY environment variable",
        ...         "Or use faster_whisper backend",
        ...     ]
        ... )
    """

    error_code: str = "AUD-201"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check backend dependencies are installed",
                "Verify API credentials if cloud backend",
                "Try alternative backend",
            ]
        super().__init__(message, context, suggestions, cause)


class TranscriptionError(BackendError):
    """
    Exception raised when transcription fails.

    This includes:
    - Transcription service errors
    - Invalid transcription results
    - Model loading failures

    Example:
        >>> raise TranscriptionError(
        ...     "Transcription failed",
        ...     context={
        ...         "backend": "faster_whisper",
        ...         "model": "large-v3",
        ...         "file": "audio.mp3",
        ...     },
        ...     suggestions=[
        ...         "Try smaller model size",
        ...         "Check available memory",
        ...         "Verify audio format",
        ...     ]
        ... )
    """

    error_code: str = "AUD-202"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check audio file format",
                "Try alternative backend",
                "Verify model availability",
            ]
        super().__init__(message, context, suggestions, cause)
