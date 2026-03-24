"""Backend-related exceptions."""

from audiocore.errors.base import AudioCoreError


class BackendError(AudioCoreError):
    """Base exception for backend-related errors."""

    error_code: str = "AUD-006"


class BackendUnavailableError(BackendError):
    """Requested backend is unavailable."""

    error_code: str = "AUD-007"


class TranscriptionError(BackendError):
    """Transcription failed."""

    error_code: str = "AUD-008"
