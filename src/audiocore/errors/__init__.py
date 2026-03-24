"""
AudioCore exception hierarchy.

All exceptions inherit from AudioCoreError and provide:
- Unique error codes (AUD-XXX)
- Contextual information
- Actionable suggestions
- Exception chaining via __cause__

Exception categories:
- Input: InvalidInputError, MediaFormatError (AUD-001 to AUD-xx9)
- Config: ConfigurationError, InvalidConfigError (AUD-100 to AUD-199)
- Backend: BackendError, BackendUnavailableError, TranscriptionError (AUD-200 to AUD-299)
- API: APIError, AuthenticationError, RateLimitError, APITimeoutError (AUD-300 to AUD-399)
- Processing: ProcessingError, VADError (AUD-400 to AUD-499)
"""

from audiocore.errors.base import AudioCoreError

# Import exception subclasses
from audiocore.errors.input import (
    InputError,
    InvalidInputError,
    MediaFormatError,
)
from audiocore.errors.config import (
    ConfigurationError,
    InvalidConfigError,
)
from audiocore.errors.backend import (
    BackendError,
    BackendUnavailableError,
    TranscriptionError,
)
from audiocore.errors.api import (
    APIError,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
)
from audiocore.errors.processing import (
    ProcessingError,
    VADError,
)

__all__ = [
    # Base
    "AudioCoreError",
    # Input exceptions
    "InputError",
    "InvalidInputError",
    "MediaFormatError",
    # Configuration exceptions
    "ConfigurationError",
    "InvalidConfigError",
    # Backend exceptions
    "BackendError",
    "BackendUnavailableError",
    "TranscriptionError",
    # API exceptions
    "APIError",
    "AuthenticationError",
    "RateLimitError",
    "APITimeoutError",
    # Processing exceptions
    "ProcessingError",
    "VADError",
]
