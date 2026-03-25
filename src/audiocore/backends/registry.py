"""Backend registry for managing transcription backend instances.

This module provides a thread-safe singleton registry for backend discovery,
retrieval, and lazy loading. The registry stores backend classes and creates
instances on demand.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from audiocore.errors import BackendUnavailableError
from audiocore.types import BackendType

if TYPE_CHECKING:
    from audiocore.backends.base import TranscriptionBackend


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
    _lock: threading.Lock = threading.Lock()  # Class-level lock for singleton

    def __new__(cls) -> BackendRegistry:
        """Create or return the singleton registry instance.

        Uses double-checked locking for thread-safe singleton pattern.

        Returns:
            The singleton BackendRegistry instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        """Initialize registry with empty backend and instance dicts.

        Only initializes once per singleton lifecycle.
        """
        if self._initialized:
            return

        # Instance-level lock for thread-safe backend instance creation
        self._instance_lock: threading.Lock = threading.Lock()
        # Store backend classes (lazy loading)
        self._backends: dict[BackendType, type[TranscriptionBackend]] = {}
        # Store backend instances (memoization)
        self._instances: dict[BackendType, TranscriptionBackend] = {}
        self._initialized = True

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
        self._backends[backend_type] = backend_class
        # Clear cached instance if backend is re-registered
        if backend_type in self._instances:
            del self._instances[backend_type]

    def get_backend(self, backend_type: BackendType) -> TranscriptionBackend:
        """Get a backend instance for the given type.

        Returns the cached instance if available, otherwise creates a new
        instance and stores it for future use (memoization).

        Args:
            backend_type: The BackendType enum value for the desired backend.

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
                instance = backend_class()
                self._instances[backend_type] = instance

        return self._instances[backend_type]

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
