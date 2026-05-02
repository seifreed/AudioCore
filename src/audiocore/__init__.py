"""
AudioCore - Audio/Video transcription engine with dual backend support.

AudioCore bridges cloud and local transcription with automatic backend
selection, handling audio extraction, VAD segmentation, and output
formatting so developers don't have to.

Public API:
    - transcribe(path, options): Synchronous transcription
    - async_transcribe(path, options): Asynchronous transcription

Configuration:
    - AppConfig: Application configuration
    - TranscriptionOptions: Transcription request options

Result Types:
    - TranscriptionResult: Complete transcription output
    - Segment: Time-segmented transcription

Types:
    - BackendType: Available backend types (OPENAI, FASTER_WHISPER, AUTO)
    - ModelSize: Model sizes (TINY, BASE, SMALL, MEDIUM, LARGE)
    - OutputFormat: Output formats (TEXT, JSON, SRT, VTT)
    - SelectionPolicy: Backend selection policies (PREFER_LOCAL, PREFER_CLOUD, AUTO)

Exceptions:
    - AudioCoreError: Base exception for all AudioCore errors
    - InputError, InvalidInputError, MediaFormatError: Input errors
    - ConfigurationError, InvalidConfigError: Config errors
    - BackendError, BackendUnavailableError, TranscriptionError: Backend errors
    - APIError, AuthenticationError, RateLimitError, APITimeoutError: API errors
    - ProcessingError, VADError, MediaError: Processing errors
    - OutputFileExistsError: Output errors
    - PipelineError, PipelineStageError, PipelineCancelledError, PartialResultError: Pipeline errors

Example:
    >>> from audiocore import transcribe, TranscriptionResult, AudioCoreError
    >>>
    >>> try:
    ...     result = transcribe("audio.mp3")
    ...     print(result.segments[0].text)
    ... except AudioCoreError as e:
    ...     print(f"[{e.error_code}] {e}")

    >>> # Asynchronous transcription
    >>> import asyncio
    >>> from audiocore import async_transcribe
    >>> result = asyncio.run(async_transcribe("audio.mp3"))
"""

__version__ = "1.0.0"

# Import exceptions first - these have no circular import issues
from audiocore.errors import (
    APIError,
    APITimeoutError,
    AudioCoreError,
    AuthenticationError,
    BackendError,
    BackendUnavailableError,
    ConfigurationError,
    InputError,
    InvalidConfigError,
    InvalidInputError,
    MediaError,
    MediaFormatError,
    OutputFileExistsError,
    PartialResultError,
    PipelineCancelledError,
    PipelineError,
    PipelineStageError,
    ProcessingError,
    RateLimitError,
    TranscriptionError,
    VADError,
)

# Import models - these have no circular import issues
from audiocore.models import Segment, TranscriptionOptions, TranscriptionResult

# Import types - these have no circular import issues
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

# Note: transcribe and async_transcribe are imported lazily via __getattr__
# to avoid circular imports at module load time

__all__ = [
    # Version
    "__version__",
    # Main functions (lazy loaded)
    "transcribe",
    "async_transcribe",
    # Result types
    "TranscriptionResult",
    "TranscriptionOptions",
    "Segment",
    # Types
    "BackendType",
    "ModelSize",
    "OutputFormat",
    "SelectionPolicy",
    # Base exception
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
    "OutputFileExistsError",
    # Pipeline exceptions
    "PipelineError",
    "PipelineStageError",
    "PipelineCancelledError",
    "PartialResultError",
]


def __getattr__(name: str):
    """Lazy import for transcribe functions and AppConfig to avoid circular imports.

    This allows importing:
    - from audiocore import transcribe, async_transcribe
    - from audiocore import AppConfig

    without triggering circular imports at module load time.
    """
    if name == "transcribe":
        from audiocore.api.transcribe import transcribe

        return transcribe
    if name == "async_transcribe":
        from audiocore.api.transcribe import async_transcribe

        return async_transcribe
    if name == "AppConfig":
        from audiocore.config import AppConfig

        return AppConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
