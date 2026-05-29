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
        - Uses class-level RLock (reentrant) for thread-safe singleton initialization
        - Uses class-level RLock for thread-safe backend instance creation
        - Safe for concurrent access from multiple threads
        - RLock allows reentrant locking (e.g., calling list_backends() while
          holding the lock in register_builtin_backends())

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
    _lock: threading.RLock = threading.RLock()
    _instance_lock: threading.RLock = threading.RLock()
    _builtins_registered: bool = False

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
                    instance._backends: dict[BackendType, type[TranscriptionBackend]] = {}
                    instance._instances: dict[BackendType, TranscriptionBackend] = {}
                    instance._instance_configs: dict[BackendType, object | None] = {}
                    cls._instance = instance
        if not hasattr(cls._instance, "_instance_configs"):
            with cls._lock:
                if not hasattr(cls._instance, "_instance_configs"):
                    cls._instance._instance_configs = {}
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
            self._register_unlocked(backend_type, backend_class)

    def _register_unlocked(
        self, backend_type: BackendType, backend_class: type[TranscriptionBackend]
    ) -> None:
        """Register a backend without acquiring the lock.

        Must only be called while holding _instance_lock.
        """
        self._backends[backend_type] = backend_class
        if backend_type in self._instances:
            del self._instances[backend_type]
            self._instance_configs.pop(backend_type, None)

    def get_backend(
        self, backend_type: BackendType, config: AppConfig | None = None
    ) -> TranscriptionBackend:
        """Get a backend instance for the given type.

        Returns the cached instance if available, otherwise creates a new
        instance and stores it for future use (memoization).

        When a config is provided that differs from the cached instance's
        config, a new instance is created and replaces the cached one. Callers
        holding references to the old instance will continue using it.

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
        # Create or replace instance with thread-safe locking
        with self._instance_lock:
            # Check if backend is registered (inside lock for thread safety)
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

            # Check for cached instance with matching config
            if backend_type in self._instances:
                cached_requested_config = self._instance_configs.get(backend_type)
                if self._requested_configs_match(cached_requested_config, config):
                    return self._instances[backend_type]

            backend_class = self._backends[backend_type]
            instance = self._create_backend_instance(backend_class, config)
            self._instances[backend_type] = instance
            self._instance_configs[backend_type] = config
            return instance

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

    @staticmethod
    def _configs_match(config_a: object, config_b: object) -> bool:
        """Compare two configs for equality, handling SecretStr correctly.

        Pydantic's default __eq__ for models with SecretStr fields compares
        by object identity for the SecretStr, not the wrapped value. This
        method ensures two configs with the same secret value are considered equal.

        Also handles the case where one config is an AppConfig and the other
        is a backend-specific sub-config by extracting the relevant sub-config.
        """
        if config_a is config_b:
            return True

        from audiocore.config import AppConfig, FasterWhisperConfig, OpenAIConfig

        # If one is AppConfig and the other is a sub-config, extract sub-config
        if isinstance(config_a, AppConfig) and not isinstance(config_b, AppConfig):
            if isinstance(config_b, OpenAIConfig):
                config_a = config_a.openai
            elif isinstance(config_b, FasterWhisperConfig):
                config_a = config_a.faster_whisper
        elif isinstance(config_b, AppConfig) and not isinstance(config_a, AppConfig):
            if isinstance(config_a, OpenAIConfig):
                config_b = config_b.openai
            elif isinstance(config_a, FasterWhisperConfig):
                config_b = config_b.faster_whisper

        # If both have model_fields, compare field-by-field to handle SecretStr
        if hasattr(config_a, "model_fields") and hasattr(config_b, "model_fields"):
            from pydantic import SecretStr

            common_fields = set(config_a.model_fields.keys()) & set(config_b.model_fields.keys())
            if not common_fields:
                # No common fields — configs are incomparable, treat as not matching
                return False

            for field_name in common_fields:
                val_a = getattr(config_a, field_name)
                val_b = getattr(config_b, field_name)
                if isinstance(val_a, SecretStr) and isinstance(val_b, SecretStr):
                    if val_a.get_secret_value() != val_b.get_secret_value():
                        return False
                elif isinstance(val_a, SecretStr) or isinstance(val_b, SecretStr):
                    return False
                elif hasattr(val_a, "model_fields") and hasattr(val_b, "model_fields"):
                    if not BackendRegistry._configs_match(val_a, val_b):
                        return False
                elif val_a != val_b:
                    return False
            return True

        # Fallback to standard equality
        return config_a == config_b

    @staticmethod
    def _requested_configs_match(
        cached_requested_config: object | None,
        requested_config: object | None,
    ) -> bool:
        """Compare the config intent used to create a cached backend instance."""
        if cached_requested_config is None or requested_config is None:
            return cached_requested_config is None and requested_config is None
        from audiocore.config import AppConfig

        if isinstance(cached_requested_config, AppConfig) != isinstance(
            requested_config, AppConfig
        ):
            return False
        return BackendRegistry._configs_match(cached_requested_config, requested_config)

    def list_backends(self) -> list[BackendType]:
        """List all registered backend types.

        Returns:
            List of BackendType enum values for registered backends.

        Example:
            >>> registry.list_backends()
            [<BackendType.OPENAI: 'openai'>, <BackendType.FASTER_WHISPER: 'faster_whisper'>]
        """
        with self._instance_lock:
            return list(self._backends.keys())

    def is_available(self, backend_type: BackendType) -> bool:
        """Check if a backend is registered and available.

        A backend is available if:
        1. It is registered in the registry
        2. Its is_available() method returns True

        Uses cached instance if available. If no cached instance exists,
        creates one inside the lock and caches it for reuse (avoids leaking
        resources from discarded temporary instances).

        Args:
            backend_type: The BackendType enum value to check.

        Returns:
            True if the backend is registered and available, False otherwise.

        Example:
            >>> if registry.is_available(BackendType.OPENAI):
            ...     backend = registry.get_backend(BackendType.OPENAI)
        """
        with self._instance_lock:
            if backend_type not in self._backends:
                return False

            # If an instance is already cached, check its availability
            if backend_type in self._instances:
                try:
                    return self._instances[backend_type].is_available()
                except Exception:
                    return False

            # No cached instance — create one inside the lock and cache it.
            # This avoids leaking resources from discarded temporary instances.
            try:
                backend_class = self._backends[backend_type]
                instance = self._create_backend_instance(backend_class, None)
                self._instances[backend_type] = instance
                self._instance_configs[backend_type] = None
                return instance.is_available()
            except Exception:
                return False

    def clear(self) -> None:
        """Clear all registered backends and cached instances.

        This is primarily used for testing to ensure test isolation.
        After clearing, built-in backends are automatically re-registered
        so the registry remains usable.

        Thread-safe: Uses the instance lock to prevent race conditions
        with other registry operations.

        Example:
            >>> registry.clear()
            >>> registry.list_backends()
            [<BackendType.OPENAI: 'openai'>, <BackendType.FASTER_WHISPER: 'faster_whisper'>]
        """
        from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
        from audiocore.backends.openai_backend import OpenAIBackend
        from audiocore.types import BackendType

        with self._instance_lock:
            self._backends.clear()
            self._instances.clear()
            self._instance_configs.clear()
            # Re-register built-in backends so the registry stays usable after clear()
            self._register_unlocked(BackendType.OPENAI, OpenAIBackend)
            self._register_unlocked(BackendType.FASTER_WHISPER, FasterWhisperBackend)

    def _reset(self) -> None:
        """Completely clear the registry including built-in backends.

        For test use only: leaves the registry empty. Call
        register_builtin_backends() to restore built-in backends.
        """
        with self._instance_lock:
            self._backends.clear()
            self._instances.clear()
            self._instance_configs.clear()
            BackendRegistry._builtins_registered = False
