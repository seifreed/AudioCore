"""
AudioCore exception hierarchy.

All exceptions inherit from AudioCoreError and provide:
- Unique error codes (AUD-XXX)
- Contextual information
- Actionable suggestions
- Exception chaining via __cause__

Exception categories:
- Input: InvalidInputError, MediaFormatError (AUD-001 to AUD-099)
- Config: ConfigurationError, InvalidConfigError (AUD-100 to AUD-199)
- Backend: BackendError, BackendUnavailableError, TranscriptionError (AUD-200 to AUD-299)
- API: APIError, AuthenticationError, RateLimitError, APITimeoutError (AUD-300 to AUD-399)
- Processing: ProcessingError, VADError (AUD-400 to AUD-499)
- Pipeline: CancelledError (AUD-500) - imported from audiocore.pipeline.cancellation
- Output: OutputFileExistsError (AUD-600), OutputDirectoryError (AUD-601)
"""

from audiocore.errors.api import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from audiocore.errors.backend import (
    BackendError,
    BackendUnavailableError,
    TranscriptionError,
)
from audiocore.errors.base import AudioCoreError
from audiocore.errors.config import (
    ConfigurationError,
    InvalidConfigError,
)

# Import exception subclasses
from audiocore.errors.input import (
    InputError,
    InvalidInputError,
    MediaFormatError,
)
from audiocore.errors.output import OutputDirectoryError, OutputFileExistsError
from audiocore.errors.processing import (
    MediaError,
    ProcessingError,
    VADError,
)

# Note: CancelledError (AUD-500) is in audiocore.pipeline.cancellation
# to avoid circular imports. Import from audiocore.pipeline.cancellation directly.
# Pipeline-specific exceptions (AUD-501 to AUD-504)
# These are imported here for convenience, but defined in audiocore.pipeline.errors
# to avoid circular imports with PipelineStage.
from audiocore.pipeline.errors import (
    PartialResultError,
    PipelineCancelledError,
    PipelineError,
    PipelineStageError,
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
    "MediaError",
    # Output exceptions
    "OutputDirectoryError",
    "OutputFileExistsError",
    # Pipeline exceptions (AUD-501 to AUD-504)
    "PipelineError",
    "PipelineStageError",
    "PipelineCancelledError",
    "PartialResultError",
]
