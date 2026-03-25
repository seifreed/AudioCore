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

from audiocore.backends.base import TranscriptionBackend, is_backend_available
from audiocore.backends.openai_backend import OpenAIBackend
from audiocore.backends.registry import BackendRegistry

__all__ = ["TranscriptionBackend", "is_backend_available", "BackendRegistry", "OpenAIBackend"]
