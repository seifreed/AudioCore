"""Unit tests for backend registry integration.

These tests verify:
- OpenAI backend is properly registered
- BackendRegistry.get_backend returns OpenAIBackend instances
- Backend availability checks work correctly
- End-to-end registry workflow
"""

from unittest.mock import MagicMock, patch

import pytest

from audiocore.backends import BackendRegistry, OpenAIBackend
from audiocore.types import BackendType


class TestBackendRegistryIntegration:
    """Test OpenAI backend integration with BackendRegistry."""

    def test_registry_returns_openai_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify get_backend(OPENAI) returns OpenAIBackend instance."""
        # Set environment for availability check
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        registry = BackendRegistry()
        registry.clear()  # Clear for test isolation

        # Register OpenAI backend
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # Get backend via registry
        backend = registry.get_backend(BackendType.OPENAI)

        # Verify type
        assert isinstance(backend, OpenAIBackend)
        assert backend.backend_type == BackendType.OPENAI

    def test_registry_list_backends_includes_openai(self) -> None:
        """Verify list_backends() includes OPENAI."""
        registry = BackendRegistry()
        registry.clear()  # Clear for test isolation

        # Register
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # List
        backends = registry.list_backends()

        # OpenAI should be present
        assert BackendType.OPENAI in backends

    def test_registry_is_available_with_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify is_available() returns True when API key provided."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        registry = BackendRegistry()
        registry.clear()
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # Backend should be available with API key
        assert registry.is_available(BackendType.OPENAI)

    def test_registry_is_available_without_key(self) -> None:
        """Verify is_available() returns False when no API key."""
        registry = BackendRegistry()
        registry.clear()
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # Clear environment
        with patch.dict("os.environ", {}, clear=True):
            assert not registry.is_available(BackendType.OPENAI)

    def test_registry_get_backend_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify backend has correct name."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        registry = BackendRegistry()
        registry.clear()
        registry.register(BackendType.OPENAI, OpenAIBackend)

        backend = registry.get_backend(BackendType.OPENAI)
        assert backend.get_name() == "OpenAI Whisper API"

    def test_registry_get_backend_model_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify backend returns valid model options."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        registry = BackendRegistry()
        registry.clear()
        registry.register(BackendType.OPENAI, OpenAIBackend)

        backend = registry.get_backend(BackendType.OPENAI)
        models = backend.get_model_options()

        assert isinstance(models, list)
        assert "whisper-1" in models

    def test_end_to_end_registry_workflow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test complete workflow: register, get, check, use."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        registry = BackendRegistry()
        registry.clear()

        # Step 1: Register backend
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # Step 2: Check availability
        assert registry.is_available(BackendType.OPENAI)

        # Step 3: Get backend
        backend = registry.get_backend(BackendType.OPENAI)

        # Step 4: Verify backend properties
        assert backend.backend_type == BackendType.OPENAI
        assert backend.get_name() == "OpenAI Whisper API"
        assert "whisper-1" in backend.get_model_options()
        assert backend.is_available()  # With key

    def test_multiple_backends_registered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test registry with multiple backend types."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        registry = BackendRegistry()
        registry.clear()

        # Register OpenAI
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # List should include OPENAI
        backends = registry.list_backends()
        assert BackendType.OPENAI in backends

        # Can retrieve OpenAI specifically
        openai_backend = registry.get_backend(BackendType.OPENAI)
        assert isinstance(openai_backend, OpenAIBackend)


class TestModuleImportSideEffects:
    """Test that importing the backends module has correct side effects."""

    def test_import_registers_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that importing audiocore.backends makes OpenAI available."""
        # Set env var for availability
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # Re-import to ensure clean state for this test
        from audiocore.backends import BackendRegistry

        registry = BackendRegistry()
        registry.clear()

        # OpenAI backend should be registered
        registry.register(BackendType.OPENAI, OpenAIBackend)
        backends = registry.list_backends()

        assert BackendType.OPENAI in backends

    def test_openai_backend_exported(self) -> None:
        """Verify OpenAIBackend is exported in __init__.py."""
        from audiocore.backends import OpenAIBackend

        # Should be able to instantiate
        backend = OpenAIBackend(api_key="sk-test")
        assert backend is not None
        assert backend.backend_type == BackendType.OPENAI
