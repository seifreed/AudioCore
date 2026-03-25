"""Transcription backend abstraction layer.

This module provides the abstract base class and utilities for
transcription backend implementations. Backends inherit from
TranscriptionBackend and implement all abstract methods.

Available backends:
- OpenAI Whisper API (Phase 6)
- Faster-Whisper local backend (Phase 7)

Example:
    >>> from audiocore.backends import TranscriptionBackend, BackendRegistry
    >>> from audiocore.types import BackendType
    >>>
    >>> class MyBackend(TranscriptionBackend):
    ...     @property
    ...     def backend_type(self) -> BackendType:
    ...         return BackendType.OPENAI
    ...
    ...     # ... implement other abstract methods
    >>>
    >>> # Register your backend
    >>> registry = BackendRegistry()
    >>> registry.register(BackendType.OPENAI, MyBackend)
"""

from audiocore.backends.availability import BackendAvailabilityChecker, BackendStatus
from audiocore.backends.base import TranscriptionBackend, is_backend_available
from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
from audiocore.backends.openai_backend import OpenAIBackend
from audiocore.backends.registry import BackendRegistry
from audiocore.backends.selector import BackendSelector, select_backend
from audiocore.types import BackendType

__all__ = [
    "TranscriptionBackend",
    "is_backend_available",
    "BackendRegistry",
    "OpenAIBackend",
    "FasterWhisperBackend",
    "BackendStatus",
    "BackendAvailabilityChecker",
    "BackendSelector",
    "select_backend",
]


def register_builtin_backends() -> None:
    """Register all built-in backends.

    This function registers all backends that are included with AudioCore.
    Currently includes:
    - OpenAI Whisper API backend (OPENAI)
    - Faster-Whisper local backend (FASTER_WHISPER)

    Call this function to ensure backends are registered before using
    BackendRegistry for backend discovery.

    Example:
        >>> from audiocore.backends import register_builtin_backends, BackendRegistry
        >>> from audiocore.types import BackendType
        >>>
        >>> register_builtin_backends()
        >>> registry = BackendRegistry()
        >>> backend = registry.get_backend(BackendType.OPENAI)
    """
    registry = BackendRegistry()
    registry.register(BackendType.OPENAI, OpenAIBackend)
    registry.register(BackendType.FASTER_WHISPER, FasterWhisperBackend)
