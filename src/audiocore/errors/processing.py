"""Processing-related exceptions."""

from audiocore.errors.base import AudioCoreError


class ProcessingError(AudioCoreError):
    """Base exception for processing-related errors."""

    error_code: str = "AUD-013"


class VADError(ProcessingError):
    """Voice Activity Detection error."""

    error_code: str = "AUD-014"
