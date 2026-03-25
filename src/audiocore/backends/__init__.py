"""Transcription backend abstraction layer.

This module provides the abstract base class and utilities for
transcription backend implementations. Backends inherit from
TranscriptionBackend and implement all abstract methods.

Available backends:
- OpenAI Whisper API (Phase 6)
- Faster-Whisper local backend (Phase 7)

Example:
    >>> from audiocore.backends import TranscriptionBackend
    >>> from audiocore.types import BackendType
    >>>
    >>> class MyBackend(TranscriptionBackend):
    ...     @property
    ...     def backend_type(self) -> BackendType:
    ...         return BackendType.OPENAI
    ...
    ...     # ... implement other abstract methods
"""

from audiocore.backends.base import TranscriptionBackend, is_backend_available

__all__ = ["TranscriptionBackend", "is_backend_available"]
