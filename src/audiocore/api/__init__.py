"""
AudioCore Public API Module.

This module provides the public API for AudioCore, enabling programmatic
use without the CLI. It re-exports all public symbols for convenience.

Main Functions:
    - transcribe(path, options): Synchronous transcription
    - async_transcribe(path, options): Asynchronous transcription

Result Types:
    - TranscriptionResult: Complete transcription output

Configuration:
    - TranscriptionOptions: Options for customizing transcription
    - BackendType: Available backend types
    - OutputFormat: Available output formats

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
    >>> from audiocore.api import transcribe, async_transcribe
    >>> from audiocore import TranscriptionResult, TranscriptionOptions, AudioCoreError
    >>>
    >>> # Synchronous transcription
    >>> result = transcribe("audio.mp3")
    >>> print(result.segments[0].text)

    >>> # Asynchronous transcription
    >>> import asyncio
    >>> result = asyncio.run(async_transcribe("audio.mp3"))
    >>> print(result.segments[0].text)
"""

# Import exceptions - these don't have circular import issues
# Note: transcribe and async_transcribe are imported lazily to avoid circular imports
# They are defined in audiocore.api.transcribe and imported when accessed
# Import convenience function that handles lazy loading
from audiocore.api.transcribe import async_transcribe, transcribe
from audiocore.errors import (
    APIError,
    APITimeoutError,
    AudioCoreError,
    AuthenticationError,
    BackendError,
    BackendUnavailableError,
    ConfigurationError,
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

# Import models - these don't have circular import issues
from audiocore.models import TranscriptionOptions, TranscriptionResult
from audiocore.pipeline.cancellation import CancellationToken

# Import progress types - these don't have circular import issues
from audiocore.pipeline.progress import PipelineStage, ProgressCallback

# Import types - these don't have circular import issues
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

# Note: AppConfig has circular import when loaded early, so import lazily
# Users should use: from audiocore.config import AppConfig

__all__ = [
    # Main functions
    "transcribe",
    "async_transcribe",
    # Result types
    "TranscriptionResult",
    "TranscriptionOptions",
    # Types
    "BackendType",
    "ModelSize",
    "OutputFormat",
    "SelectionPolicy",
    # Progress types
    "ProgressCallback",
    "PipelineStage",
    "CancellationToken",
    # Base exception
    "AudioCoreError",
    # Input exceptions
    "InvalidInputError",
    "MediaFormatError",
    "InputError",
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
    """Lazy import for AppConfig to avoid circular imports."""
    if name == "AppConfig":
        from audiocore.config import AppConfig

        return AppConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
