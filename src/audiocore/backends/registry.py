"""Backend registry for managing transcription backend instances.

This module provides a thread-safe singleton registry for backend discovery,
retrieval, and lazy loading. The registry stores backend classes and creates
instances on demand.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from audiocore.errors import BackendUnavailableError

if TYPE_CHECKING:
    from audiocore.backends.base import TranscriptionBackend
    from audiocore.config import AppConfig
    from audiocore.types import BackendType


class BackendRegistry:
    """Thread-safe singleton registry for transcription backends.

    Manages backend registration, discovery, and lazy instantiation. Backends
    are registered by type and created on first access.

    The registry uses lazy loading to avoid importing backend dependencies
    until needed. Backend classes are stored and instances are created on
    first call to get_backend().

    Thread Safety:
        - Uses class-level Lock for thread-safe singleton initialization
        - Uses instance-level Lock for thread-safe backend instance creation
        - Safe for concurrent access from multiple threads

    Attributes:
        _instance: Singleton instance (class-level).
        _lock: Thread lock for singleton initialization (class-level).
        _backends: Dict mapping BackendType to backend class.
        _instances: Dict mapping BackendType to backend instance (memoized).

    Example:
        >>> registry = BackendRegistry()
        >>> registry.register(BackendType.OPENAI, OpenAIBackend)
        >>> backend = registry.get_backend(BackendType.OPENAI)
        >>> backend.transcribe("audio.mp3", options)
    """

    _instance: BackendRegistry | None = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool
    _instance_lock: threading.Lock
    _backends: dict[BackendType, type[TranscriptionBackend]]
    _instances: dict[BackendType, TranscriptionBackend]

    def __new__(cls) -> BackendRegistry:
        """Create or return the singleton registry instance.

        Uses double-checked locking for thread-safe singleton pattern.
        Initialization is done atomically within __new__ to prevent
        race conditions between __new__ and __init__.

        Returns:
            The singleton BackendRegistry instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    # Initialize within the lock to prevent race conditions
                    instance._instance_lock = threading.Lock()
                    instance._backends: dict[BackendType, type[TranscriptionBackend]] = {}
                    instance._instances: dict[BackendType, TranscriptionBackend] = {}
                    instance._initialized = True
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        """No-op initialization. All setup is done in __new__ for thread safety."""
        # All initialization is done in __new__ to prevent race conditions
        # where __init__ could re-initialize between __new__ setting _instance
        # and setting _initialized = True
        pass

    def register(
        self, backend_type: BackendType, backend_class: type[TranscriptionBackend]
    ) -> None:
        """Register a backend class for a given backend type.

        Backends are registered as classes, not instances. Instances are
        created lazily on first call to get_backend().

        Args:
            backend_type: The BackendType enum value for this backend.
            backend_class: The TranscriptionBackend subclass to register.

        Note:
            - Re-registering a backend type overwrites the previous registration
            - The backend instance cache is cleared when re-registering

        Example:
            >>> registry.register(BackendType.OPENAI, OpenAIBackend)
        """
        with self._instance_lock:
            self._backends[backend_type] = backend_class
            # Clear cached instance if backend is re-registered
            if backend_type in self._instances:
                del self._instances[backend_type]

    def get_backend(
        self, backend_type: BackendType, config: AppConfig | None = None
    ) -> TranscriptionBackend:
        """Get a backend instance for the given type.

        Returns the cached instance if available, otherwise creates a new
        instance and stores it for future use (memoization).

        Args:
            backend_type: The BackendType enum value for the desired backend.
            config: Optional AppConfig to pass to the backend constructor.
                The backend receives the relevant sub-config extracted from
                AppConfig (e.g., OpenAIConfig for OPENAI, FasterWhisperConfig
                for FASTER_WHISPER).

        Returns:
            An instance of the registered backend.

        Raises:
            BackendUnavailableError: If the backend type is not registered.

        Example:
            >>> backend = registry.get_backend(BackendType.OPENAI)
            >>> result = backend.transcribe("audio.mp3", options)
        """
        # Check if backend is registered
        if backend_type not in self._backends:
            raise BackendUnavailableError(
                f"Backend {backend_type.value} is not registered",
                context={
                    "backend_type": backend_type.value,
                    "registered": list(self._backends.keys()),
                },
                suggestions=[
                    f"Register {backend_type.value} backend before use",
                    "Use BackendRegistry.register() to add backends",
                ],
            )

        # Return cached instance if available
        if backend_type in self._instances:
            return self._instances[backend_type]

        # Create new instance with thread-safe locking
        with self._instance_lock:
            # Double-checked locking pattern
            if backend_type not in self._instances:
                backend_class = self._backends[backend_type]
                instance = self._create_backend_instance(backend_class, config)
                self._instances[backend_type] = instance

        return self._instances[backend_type]

    @staticmethod
    def _create_backend_instance(
        backend_class: type[TranscriptionBackend],
        config: AppConfig | None,
    ) -> TranscriptionBackend:
        """Create a backend instance with the appropriate config.

        Extracts the relevant sub-config from AppConfig for each backend type.
        """
        if config is None:
            return backend_class()

        # Map AppConfig to backend-specific config
        from audiocore.config import AppConfig

        if isinstance(config, AppConfig):
            # OpenAIBackend and FasterWhisperBackend accept AppConfig
            # and extract their own sub-config internally
            return backend_class(config=config)

        # Fallback: pass config directly
        return backend_class(config=config)

    def list_backends(self) -> list[BackendType]:
        """List all registered backend types.

        Returns:
            List of BackendType enum values for registered backends.

        Example:
            >>> registry.list_backends()
            [<BackendType.OPENAI: 'openai'>, <BackendType.FASTER_WHISPER: 'faster_whisper'>]
        """
        return list(self._backends.keys())

    def is_available(self, backend_type: BackendType) -> bool:
        """Check if a backend is registered and available.

        A backend is available if:
        1. It is registered in the registry
        2. Its is_available() method returns True

        Args:
            backend_type: The BackendType enum value to check.

        Returns:
            True if the backend is registered and available, False otherwise.

        Example:
            >>> if registry.is_available(BackendType.OPENAI):
            ...     backend = registry.get_backend(BackendType.OPENAI)
        """
        # Check if backend is registered
        if backend_type not in self._backends:
            return False

        # Get backend instance and check availability
        try:
            backend = self.get_backend(backend_type)
            return backend.is_available()
        except Exception:
            # If any error occurs during availability check, backend is unavailable
            return False

    def clear(self) -> None:
        """Clear all registered backends and cached instances.

        This is primarily used for testing to ensure test isolation.

        Thread-safe: Uses the instance lock to prevent concurrent modification.

        Example:
            >>> registry.clear()
            >>> registry.list_backends()
            []
        """
        with self._instance_lock:
            self._backends.clear()
            self._instances.clear()
            BackendRegistry._instance = None
