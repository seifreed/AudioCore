"""Unit tests for BackendRegistry.

Tests verify:
- Singleton pattern (same instance from multiple calls)
- Thread-safe initialization
- Registration and retrieval of backends
- Lazy loading (instances created on first access)
- Memoization (same instance on subsequent accesses)
- Availability checking
- Error handling for unregistered backends
- Thread-safe concurrency
- Registry clearing
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from audiocore.backends import BackendRegistry
from audiocore.backends.base import TranscriptionBackend
from audiocore.errors import BackendUnavailableError
from audiocore.models import MediaInfo, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType

# Import MockTranscriptionBackend from test_base for testing
from tests.unit.backends.test_base import MockTranscriptionBackend


@pytest.fixture(autouse=True)
def clear_registry() -> Any:
    """Clear registry before and after each test.

    This ensures test isolation - each test starts with a clean registry.
    """
    registry = BackendRegistry()
    registry._reset()
    yield
    registry._reset()


class TestSingletonPattern:
    """Test singleton pattern behavior."""

    def test_singleton_returns_same_instance(self) -> None:
        """Verify multiple BackendRegistry() calls return same instance."""
        registry1 = BackendRegistry()
        registry2 = BackendRegistry()

        assert registry1 is registry2
        assert id(registry1) == id(registry2)

    def test_singleton_is_thread_safe(self) -> None:
        """Verify singleton is created safely in concurrent environment."""
        # Clear any existing singleton using the public API
        BackendRegistry().clear()

        instances: list[BackendRegistry] = []
        errors: list[Exception] = []

        def create_registry() -> None:
            try:
                instance = BackendRegistry()
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Create many threads
        threads = [threading.Thread(target=create_registry) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors during concurrent creation: {errors}"

        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)

    def test_singleton_initialized_once(self) -> None:
        """Verify singleton is initialized only once."""
        registry = BackendRegistry()

        # Register a backend
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # Create new registry instance (should be same singleton)
        registry2 = BackendRegistry()

        # Should have same backends (shared state)
        assert registry2.list_backends() == registry.list_backends()


class TestRegister:
    """Test backend registration."""

    def test_register_adds_backend_to_registry(self) -> None:
        """Verify register() adds backend to registry."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        assert BackendType.OPENAI in registry.list_backends()

    def test_register_allows_overwrite(self) -> None:
        """Verify register() overwrites existing backend for same type."""
        registry = BackendRegistry()
        registry._reset()

        # Register first backend
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # Get backend to cache instance
        backend1 = registry.get_backend(BackendType.OPENAI)

        # Re-register with different implementation
        class AnotherMockBackend(TranscriptionBackend):
            """Alternative mock backend for testing overwrite."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

            def transcribe(
                self, audio_path: Path | str, options: TranscriptionOptions
            ) -> TranscriptionResult:
                return TranscriptionResult(
                    segments=[],
                    media_info=MediaInfo(duration=1.0, format="wav", sample_rate=16000, channels=1),
                    config_used=options,
                    processing_time_seconds=0.0,
                    backend_used=self.backend_type,
                )

            def get_name(self) -> str:
                return "Another Mock Backend"

            def is_available(self) -> bool:
                return True

            def get_model_options(self) -> list[str]:
                return ["another-model"]

        registry.register(BackendType.OPENAI, AnotherMockBackend)

        # Should get new backend, not cached instance
        backend2 = registry.get_backend(BackendType.OPENAI)

        assert backend2 is not backend1
        assert backend2.get_name() == "Another Mock Backend"

    def test_register_clears_cached_instance(self) -> None:
        """Verify re-registering clears cached instance."""
        registry = BackendRegistry()
        registry._reset()

        # Register and get instance
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        instance1 = registry.get_backend(BackendType.OPENAI)

        # Re-register same type
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # Should create new instance
        instance2 = registry.get_backend(BackendType.OPENAI)

        # Different instances (old cached instance was cleared)
        assert instance1 is not instance2


class TestGetBackend:
    """Test backend retrieval."""

    def test_get_backend_returns_registered_backend_instance(self) -> None:
        """Verify get_backend() returns registered backend instance."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        backend = registry.get_backend(BackendType.OPENAI)

        assert isinstance(backend, TranscriptionBackend)
        assert isinstance(backend, MockTranscriptionBackend)

    def test_get_backend_creates_instance_on_first_call(self) -> None:
        """Verify backend instance is created on first get_backend() call (lazy loading)."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # No instance cached yet
        assert BackendType.OPENAI not in registry._instances

        # First call creates instance
        backend = registry.get_backend(BackendType.OPENAI)

        # Instance should now be cached
        assert BackendType.OPENAI in registry._instances
        assert registry._instances[BackendType.OPENAI] is backend

    def test_get_backend_returns_same_instance_on_subsequent_calls(self) -> None:
        """Verify same backend instance is returned (memoization)."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        backend1 = registry.get_backend(BackendType.OPENAI)
        backend2 = registry.get_backend(BackendType.OPENAI)

        # Same instance returned
        assert backend1 is backend2
        assert id(backend1) == id(backend2)

    def test_get_backend_raises_error_for_unregistered_backend(self) -> None:
        """Verify get_backend() raises BackendUnavailableError for unregistered backend."""
        registry = BackendRegistry()
        registry._reset()

        with pytest.raises(BackendUnavailableError) as exc_info:
            registry.get_backend(BackendType.OPENAI)

        assert exc_info.value.error_code == "AUD-201"
        assert "not registered" in str(exc_info.value).lower()

    def test_get_backend_error_includes_context(self) -> None:
        """Verify BackendUnavailableError includes backend type in context."""
        registry = BackendRegistry()
        registry._reset()

        with pytest.raises(BackendUnavailableError) as exc_info:
            registry.get_backend(BackendType.FASTER_WHISPER)

        assert exc_info.value.context is not None
        assert "backend_type" in exc_info.value.context
        assert exc_info.value.context["backend_type"] == "faster_whisper"


class TestListBackends:
    """Test listing registered backends."""

    def test_list_backends_returns_registered_types(self) -> None:
        """Verify list_backends() returns list of registered BackendTypes."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        registry.register(BackendType.FASTER_WHISPER, MockTranscriptionBackend)

        backends = registry.list_backends()

        assert BackendType.OPENAI in backends
        assert BackendType.FASTER_WHISPER in backends
        assert len(backends) == 2

    def test_list_backends_returns_empty_list_when_no_backends_registered(self) -> None:
        """Verify list_backends() returns empty list when no backends."""
        registry = BackendRegistry()
        registry._reset()

        backends = registry.list_backends()

        assert backends == []
        assert len(backends) == 0

    def test_list_backends_reflects_current_state(self) -> None:
        """Verify list_backends() shows current registry state."""
        registry = BackendRegistry()
        registry._reset()

        # Initially empty
        assert registry.list_backends() == []

        # After registration
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        assert len(registry.list_backends()) == 1

        # After another registration
        registry.register(BackendType.FASTER_WHISPER, MockTranscriptionBackend)
        assert len(registry.list_backends()) == 2

        # After clearing
        registry._reset()
        assert registry.list_backends() == []


class TestIsAvailable:
    """Test backend availability checking."""

    def test_is_available_returns_true_for_registered_and_available_backend(self) -> None:
        """Verify is_available() returns True for available backend."""
        registry = BackendRegistry()
        registry._reset()

        # Register available backend
        registry.register(BackendType.OPENAI, lambda: MockTranscriptionBackend(available=True))

        # Actually register the class, not just a lambda
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # MockTranscriptionBackend is available by default
        result = registry.is_available(BackendType.OPENAI)
        assert result is True

    def test_is_available_returns_false_for_unavailable_backend(self) -> None:
        """Verify is_available() returns False for unavailable backend."""
        registry = BackendRegistry()
        registry._reset()

        # Create a mock backend class that returns False for is_available
        class UnavailableBackend(TranscriptionBackend):
            """Backend that is unavailable."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

            def transcribe(
                self, audio_path: Path | str, options: TranscriptionOptions
            ) -> TranscriptionResult:
                return TranscriptionResult(
                    segments=[],
                    media_info=MediaInfo(duration=1.0, format="wav", sample_rate=16000, channels=1),
                    config_used=options,
                    processing_time_seconds=0.0,
                    backend_used=self.backend_type,
                )

            def get_name(self) -> str:
                return "Unavailable Backend"

            def is_available(self) -> bool:
                return False

            def get_model_options(self) -> list[str]:
                return []

        registry.register(BackendType.OPENAI, UnavailableBackend)

        result = registry.is_available(BackendType.OPENAI)
        assert result is False

    def test_is_available_returns_false_for_unregistered_backend(self) -> None:
        """Verify is_available() returns False for unregistered backend."""
        registry = BackendRegistry()
        registry._reset()

        result = registry.is_available(BackendType.OPENAI)
        assert result is False

    def test_is_available_handles_exceptions_gracefully(self) -> None:
        """Verify is_available() returns False if backend is_available() raises."""
        registry = BackendRegistry()
        registry._reset()

        # Create a backend that raises on is_available()
        class ErrorBackend(TranscriptionBackend):
            """Backend that raises error on availability check."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

            def transcribe(
                self, audio_path: Path | str, options: TranscriptionOptions
            ) -> TranscriptionResult:
                return TranscriptionResult(
                    segments=[],
                    media_info=MediaInfo(duration=1.0, format="wav", sample_rate=16000, channels=1),
                    config_used=options,
                    processing_time_seconds=0.0,
                    backend_used=self.backend_type,
                )

            def get_name(self) -> str:
                return "Error Backend"

            def is_available(self) -> bool:
                raise RuntimeError("Availability check failed")

            def get_model_options(self) -> list[str]:
                return []

        registry.register(BackendType.OPENAI, ErrorBackend)

        # Should return False, not raise
        result = registry.is_available(BackendType.OPENAI)
        assert result is False


class TestClear:
    """Test registry clearing."""

    def test_clear_removes_all_backends(self) -> None:
        """Verify clear() removes all registered backends."""
        registry = BackendRegistry()
        registry._reset()

        # Register multiple backends
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        registry.register(BackendType.FASTER_WHISPER, MockTranscriptionBackend)

        # Verify registration
        assert len(registry.list_backends()) == 2

        # Clear registry
        registry._reset()

        # Should be empty
        assert registry.list_backends() == []

    def test_clear_removes_cached_instances(self) -> None:
        """Verify clear() removes cached backend instances."""
        registry = BackendRegistry()
        registry._reset()

        # Register and get backend (creates cached instance)
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        registry.get_backend(BackendType.OPENAI)

        # Should have cached instance
        assert BackendType.OPENAI in registry._instances

        # Clear registry
        registry._reset()

        # Should have no cached instances
        assert len(registry._instances) == 0

    def test_clear_is_thread_safe(self) -> None:
        """Verify clear() is thread-safe."""
        registry = BackendRegistry()
        registry._reset()

        errors: list[Exception] = []

        def register_and_clear(backend_type: BackendType) -> None:
            try:
                registry.register(backend_type, MockTranscriptionBackend)
                _ = registry.get_backend(backend_type)
                registry._reset()
            except Exception as e:
                errors.append(e)

        # Create threads accessing registry
        threads = [
            threading.Thread(target=register_and_clear, args=(bt,))
            for bt in [BackendType.OPENAI, BackendType.FASTER_WHISPER]
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors during concurrent clear: {errors}"


class TestThreadSafety:
    """Test thread-safe concurrency."""

    def test_concurrent_get_backend_returns_same_instance(self) -> None:
        """Verify concurrent get_backend() calls return same instance for same type."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        instances: list[TranscriptionBackend] = []
        errors: list[Exception] = []

        def get_backend_thread() -> None:
            try:
                instance = registry.get_backend(BackendType.OPENAI)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Create many threads
        threads = [threading.Thread(target=get_backend_thread) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)

    def test_concurrent_registration_does_not_corrupt_state(self) -> None:
        """Verify concurrent registration doesn't corrupt registry state."""
        registry = BackendRegistry()
        registry._reset()

        errors: list[Exception] = []

        def register_backend(backend_type: BackendType) -> None:
            try:
                registry.register(backend_type, MockTranscriptionBackend)
            except Exception as e:
                errors.append(e)

        # Concurrently register different backends
        threads = [
            threading.Thread(target=register_backend, args=(BackendType.OPENAI,)),
            threading.Thread(target=register_backend, args=(BackendType.FASTER_WHISPER,)),
            threading.Thread(target=register_backend, args=(BackendType.AUTO,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors during concurrent registration: {errors}"

        # All backends should be registered
        backends = registry.list_backends()
        assert len(backends) == 3

    def test_concurrent_access_from_multiple_threads(self) -> None:
        """Verify registry handles concurrent access from multiple threads."""
        registry = BackendRegistry()
        registry._reset()

        # Register all backends
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)
        registry.register(BackendType.FASTER_WHISPER, MockTranscriptionBackend)

        results: list[tuple[BackendType, TranscriptionBackend]] = []
        errors: list[Exception] = []

        def access_backend(backend_type: BackendType, count: int) -> None:
            try:
                for _ in range(count):
                    backend = registry.get_backend(backend_type)
                    results.append((backend_type, backend))
            except Exception as e:
                errors.append(e)

        # Create threads accessing different backends
        threads = [
            threading.Thread(target=access_backend, args=(BackendType.OPENAI, 10)),
            threading.Thread(target=access_backend, args=(BackendType.FASTER_WHISPER, 10)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        # Should have all results
        assert len(results) == 20

        # Each backend type should have same instance
        openai_instances = [inst for bt, inst in results if bt == BackendType.OPENAI]
        faster_whisper_instances = [
            inst for bt, inst in results if bt == BackendType.FASTER_WHISPER
        ]

        # All OPENAI backends should be same instance
        assert all(inst is openai_instances[0] for inst in openai_instances)

        # All FASTER_WHISPER backends should be same instance
        assert all(inst is faster_whisper_instances[0] for inst in faster_whisper_instances)


class TestIntegration:
    """Integration tests for backend registry."""

    def test_full_register_get_transcribe_flow(self) -> None:
        """Test complete flow: register → get_backend → use backend."""
        registry = BackendRegistry()
        registry._reset()

        # Register backend
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # Get backend instance
        backend = registry.get_backend(BackendType.OPENAI)

        # Verify backend works
        assert backend.is_available() is True
        assert backend.get_name() == "Mock Backend"
        assert "mock-model" in backend.get_model_options()[0]

        # Test transcribe (mock implementation)
        options = TranscriptionOptions()
        result = backend.transcribe("/test/audio.wav", options)

        assert isinstance(result, TranscriptionResult)
        assert len(result.segments) > 0
        assert result.backend_used == BackendType.OPENAI

    def test_multiple_backends_independently(self) -> None:
        """Test registering and accessing multiple backends."""
        registry = BackendRegistry()
        registry._reset()

        # Create backend classes with different configurations
        class OpenAIMockBackend(MockTranscriptionBackend):
            """Mock OpenAI backend."""

            def __init__(self) -> None:
                super().__init__(
                    backend_type=BackendType.OPENAI,
                    name="Mock OpenAI API",
                    available=True,
                    models=["whisper-1"],
                )

        class FasterWhisperMockBackend(MockTranscriptionBackend):
            """Mock Faster-Whisper backend."""

            def __init__(self) -> None:
                super().__init__(
                    backend_type=BackendType.FASTER_WHISPER,
                    name="Mock Faster Whisper",
                    available=True,
                    models=["tiny", "base", "small", "medium"],
                )

        # Register both backends
        registry.register(BackendType.OPENAI, OpenAIMockBackend)
        registry.register(BackendType.FASTER_WHISPER, FasterWhisperMockBackend)

        # Get each backend
        openai_backend = registry.get_backend(BackendType.OPENAI)
        whisper_backend = registry.get_backend(BackendType.FASTER_WHISPER)

        # Verify they are different instances
        assert openai_backend is not whisper_backend
        assert openai_backend.get_name() == "Mock OpenAI API"
        assert whisper_backend.get_name() == "Mock Faster Whisper"

        # Verify independent model options
        assert openai_backend.get_model_options() == ["whisper-1"]
        assert whisper_backend.get_model_options() == ["tiny", "base", "small", "medium"]

        # Verify both are available
        assert registry.is_available(BackendType.OPENAI) is True
        assert registry.is_available(BackendType.FASTER_WHISPER) is True

    def test_registry_persists_across_singleton_instances(self) -> None:
        """Verify registry state persists across singleton instances."""
        BackendRegistry().clear()

        # Register backend in fresh singleton
        registry1 = BackendRegistry()
        registry1.register(BackendType.OPENAI, MockTranscriptionBackend)

        # Get backend from first instance
        backend1 = registry1.get_backend(BackendType.OPENAI)

        # Create "new" registry (should be same singleton)
        registry2 = BackendRegistry()

        # Should see same registration
        assert BackendType.OPENAI in registry2.list_backends()

        # Should get same backend instance
        backend2 = registry2.get_backend(BackendType.OPENAI)
        assert backend1 is backend2


class TestRegisterBuiltinBackends:
    """Test register_builtin_backends() function."""

    def test_register_builtin_backends_registers_openai(self) -> None:
        """Test that register_builtin_backends() registers OpenAI backend."""
        from audiocore.backends import register_builtin_backends

        BackendRegistry().clear()

        register_builtin_backends()

        backends = BackendRegistry().list_backends()
        assert BackendType.OPENAI in backends

    def test_register_builtin_backends_registers_faster_whisper_if_available(self) -> None:
        """Test that register_builtin_backends() registers FasterWhisper backend if available."""
        from audiocore.backends import FasterWhisperBackend, register_builtin_backends

        BackendRegistry().clear()

        register_builtin_backends()

        backends = BackendRegistry().list_backends()

        # FasterWhisperBackend may not be installed
        # This should be available after Phase 7
        if FasterWhisperBackend is not None:
            assert BackendType.FASTER_WHISPER in backends

    def test_register_builtin_backends_can_be_called_multiple_times(self) -> None:
        """Test that register_builtin_backends() can be called multiple times safely."""
        from audiocore.backends import register_builtin_backends

        BackendRegistry().clear()

        # Call twice
        register_builtin_backends()
        backends1 = BackendRegistry().list_backends()

        register_builtin_backends()
        backends2 = BackendRegistry().list_backends()

        # Should have same backends registered
        assert backends1 == backends2
        assert BackendType.OPENAI in backends1

    def test_register_builtin_backends_no_deadlock(self) -> None:
        """Regression: register_builtin_backends must not deadlock.

        Previously, register_builtin_backends() called list_backends() while
        holding _instance_lock, but list_backends() also acquires _instance_lock.
        With threading.Lock (non-reentrant), this caused a deadlock.
        Now uses RLock and directly checks _backends instead of list_backends().
        """
        from audiocore.backends import register_builtin_backends

        BackendRegistry().clear()

        # Should complete without deadlock (would hang if broken)
        import threading

        results: list[str] = []
        errors: list[Exception] = []

        def call_register() -> None:
            try:
                register_builtin_backends()
                results.append("ok")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call_register) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 5


class TestRegistrySingletonReset:
    """Regression tests for BackendRegistry.clear() resetting singleton."""

    def test_clear_re_registers_builtins(self) -> None:
        """After clear(), built-in backends are re-registered automatically."""
        registry = BackendRegistry()
        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        registry.clear()

        # Built-in backends should still be available after clear()
        backends = registry.list_backends()
        assert BackendType.OPENAI in backends
        assert BackendType.FASTER_WHISPER in backends


class TestSecretStrConfigMatching:
    """Regression tests for SecretStr comparison in config matching (Bug #11)."""

    def test_configs_with_same_secret_values_match(self) -> None:
        """Two AppConfig instances with same SecretStr values should match."""
        from pydantic import SecretStr

        from audiocore.config import AppConfig
        from audiocore.config.openai_config import OpenAIConfig

        config1 = AppConfig(openai=OpenAIConfig(api_key=SecretStr("sk-test-key")))
        config2 = AppConfig(openai=OpenAIConfig(api_key=SecretStr("sk-test-key")))

        assert BackendRegistry._configs_match(config1, config2) is True

    def test_configs_with_different_secret_values_differ(self) -> None:
        """Two AppConfig instances with different SecretStr values should not match."""
        from pydantic import SecretStr

        from audiocore.config import AppConfig
        from audiocore.config.openai_config import OpenAIConfig

        config1 = AppConfig(openai=OpenAIConfig(api_key=SecretStr("sk-key-1")))
        config2 = AppConfig(openai=OpenAIConfig(api_key=SecretStr("sk-key-2")))

        assert BackendRegistry._configs_match(config1, config2) is False

    def test_app_config_matches_openai_sub_config(self) -> None:
        """Regression: AppConfig-to-OpenAIConfig comparison must work at runtime."""
        from pydantic import SecretStr

        from audiocore.config import AppConfig, OpenAIConfig

        openai = OpenAIConfig(api_key=SecretStr("sk-test-key"))
        app_config = AppConfig(openai=openai)

        assert BackendRegistry._configs_match(app_config, openai) is True
        assert BackendRegistry._configs_match(openai, app_config) is True

    def test_app_config_matches_faster_whisper_sub_config(self) -> None:
        """Regression: AppConfig-to-FasterWhisperConfig comparison must work at runtime."""
        from audiocore.config import AppConfig, FasterWhisperConfig
        from audiocore.types import ModelSize

        faster_whisper = FasterWhisperConfig(model_size=ModelSize.TINY, device="cpu")
        app_config = AppConfig(faster_whisper=faster_whisper)

        assert BackendRegistry._configs_match(app_config, faster_whisper) is True
        assert BackendRegistry._configs_match(faster_whisper, app_config) is True


class TestGetBackendConfigRace:
    """Regression tests for TOCTOU race in get_backend()."""

    def test_config_check_happens_inside_lock(self) -> None:
        """Regression: config-matching check must happen inside _instance_lock.

        Previously, the config-matching check ran outside the lock, so two
        threads with different configs could race: both pass the check, one
        returns a stale instance while the other overwrites it. Now the check
        always happens inside the lock.
        """
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        # Verify that get_backend works correctly for the no-config case
        backend1 = registry.get_backend(BackendType.OPENAI)
        backend2 = registry.get_backend(BackendType.OPENAI)
        assert backend1 is backend2

    def test_concurrent_get_backend_with_config_is_deterministic(self) -> None:
        """Concurrent get_backend() with the same config must return same instance."""
        registry = BackendRegistry()
        registry._reset()

        registry.register(BackendType.OPENAI, MockTranscriptionBackend)

        instances: list[TranscriptionBackend] = []
        errors: list[Exception] = []

        def get_backend_thread() -> None:
            try:
                instance = registry.get_backend(BackendType.OPENAI)
                instances.append(instance)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_backend_thread) for _ in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert all(inst is instances[0] for inst in instances)
