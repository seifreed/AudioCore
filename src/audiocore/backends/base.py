"""Abstract base class for transcription backends.

This module defines the TranscriptionBackend ABC that all transcription
backends must implement. It establishes a consistent interface for:

- Transcribing audio/video files
- Checking backend availability
- Retrieving backend metadata
- Getting valid model options

The abstraction allows seamless switching between backends (OpenAI,
faster-whisper, etc.) without changes to calling code.
"""

from __future__ import annotations

import abc
import logging
from typing import TYPE_CHECKING

from audiocore.errors import InvalidInputError

if TYPE_CHECKING:
    from pathlib import Path

    from audiocore.models import TranscriptionOptions, TranscriptionResult
    from audiocore.types import BackendType

logger = logging.getLogger(__name__)


class TranscriptionBackend(abc.ABC):
    """Abstract base class for transcription backends.

    All transcription backends must inherit from this class and implement
    all abstract methods. This establishes a consistent interface for
    audio/video transcription across different providers.

    The ABC ensures that any backend implementation provides:
    - Backend type identification
    - Availability checking
    - Model option discovery
    - Transcription execution

    Attributes:
        backend_type: The BackendType enum value for this backend.

    Example:
        >>> class OpenAIBackend(TranscriptionBackend):
        ...     @property
        ...     def backend_type(self) -> BackendType:
        ...         return BackendType.OPENAI
        ...
        ...     def transcribe(self, audio_path, options):
        ...         # Implementation here
        ...         pass
        ...
        ...     def get_name(self) -> str:
        ...         return "OpenAI Whisper API"
        ...
        ...     def is_available(self) -> bool:
        ...         return bool(os.environ.get("OPENAI_API_KEY"))
        ...
        ...     def get_model_options(self) -> list[str]:
        ...         return ["whisper-1"]

    Note:
        Cannot instantiate TranscriptionBackend directly - must subclass
        and implement all abstract methods.
    """

    @property
    @abc.abstractmethod
    def backend_type(self) -> BackendType:
        """Return the backend type identifier.

        Returns:
            BackendType: The enum value identifying this backend type.

        Example:
            >>> backend.backend_type
            <BackendType.OPENAI: 'openai'>
        """
        ...

    @abc.abstractmethod
    def transcribe(
        self, audio_path: Path | str, options: TranscriptionOptions
    ) -> TranscriptionResult:
        """Transcribe an audio/video file.

        Args:
            audio_path: Path to the audio/video file to transcribe.
                Accepts both Path objects and string paths.
            options: Transcription configuration options including
                language, model size, output format, etc.

        Returns:
            TranscriptionResult: Complete transcription result including
                segments, media info, and processing metadata.

        Raises:
            BackendUnavailableError: If the backend is not available
                (check is_available() first).
            TranscriptionError: If transcription fails for any reason.

        Example:
            >>> from audiocore.models import TranscriptionOptions
            >>> result = backend.transcribe("audio.mp3", TranscriptionOptions())
            >>> result.segments[0].text
            'Hello, world!'
        """
        ...

    @abc.abstractmethod
    def get_name(self) -> str:
        """Return a human-readable backend name.

        Returns:
            str: Display name for this backend (e.g., "OpenAI Whisper API").

        Example:
            >>> backend.get_name()
            'OpenAI Whisper API'
        """
        ...

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is ready to use.

        This method checks whether all required dependencies, credentials,
        and resources are available for the backend to function.

        Returns:
            bool: True if the backend can be used for transcription,
                False otherwise.

        Example:
            >>> if backend.is_available():
            ...     result = backend.transcribe(audio_path, options)
            ... else:
            ...     print("Backend unavailable")
        """
        ...

    @abc.abstractmethod
    def get_model_options(self) -> list[str]:
        """Return list of valid model names for this backend.

        Returns:
            list[str]: List of model identifiers that can be used with
                this backend.

        Example:
            >>> backend.get_model_options()
            ['whisper-1', 'whisper-large-v3']
        """
        ...

    def _validate_audio_file(self, audio_path: Path) -> None:
        """Validate that audio_path exists and is a regular file.

        Shared by concrete backends; the backend tag in the error context is
        taken from backend_type so each subclass reports its own name.

        Raises:
            InvalidInputError: If the path is missing or is not a file.
        """
        backend = self.backend_type.value
        if not audio_path.exists():
            raise InvalidInputError(
                f"Audio file not found: {audio_path}",
                context={"file_path": str(audio_path), "backend": backend},
                suggestions=[
                    "Verify the file path is correct",
                    "Check the file exists",
                ],
            )
        if not audio_path.is_file():
            raise InvalidInputError(
                f"Audio path is not a file: {audio_path}",
                context={"file_path": str(audio_path), "backend": backend},
                suggestions=[
                    "Provide an audio file path, not a directory",
                    "Verify the file path is correct",
                ],
            )


def is_backend_available(backend: TranscriptionBackend) -> bool:
    """Check if a backend is available with error handling.

    Safely checks backend availability, returning False if any
    exception occurs during the check. This is useful for scenarios
    where backend initialization may fail unexpectedly.

    Args:
        backend: The backend to check availability for.

    Returns:
        bool: True if the backend is available, False otherwise.

    Example:
        >>> from audiocore.backends import is_backend_available
        >>> if is_backend_available(backend):
        ...     result = backend.transcribe(audio_path, options)
        ... else:
        ...     print("Backend not available")

    Note:
        Logs a warning if is_available() raises an exception.
    """
    try:
        return backend.is_available()
    except Exception as e:
        logger.warning(
            f"Exception checking availability for backend {backend.__class__.__name__}: {e}"
        )
        return False
