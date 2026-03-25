"""Unit tests for TranscriptionBackend abstract base class.

These tests verify:
- ABC cannot be instantiated directly
- Subclasses must implement all abstract methods
- Abstract method signatures are correct
- Helper function behavior
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import logging

import pytest

from audiocore.backends.base import TranscriptionBackend, is_backend_available
from audiocore.errors import BackendUnavailableError
from audiocore.models import TranscriptionOptions, TranscriptionResult, MediaInfo, Segment
from audiocore.types import BackendType


class MockTranscriptionBackend(TranscriptionBackend):
    """Mock implementation of TranscriptionBackend for testing.

    Implements all abstract methods with configurable behavior for
    unit testing backend-related functionality.
    """

    def __init__(
        self,
        backend_type: BackendType = BackendType.OPENAI,
        name: str = "Mock Backend",
        available: bool = True,
        models: list[str] | None = None,
    ) -> None:
        """Initialize mock backend with configurable properties.

        Args:
            backend_type: The backend type to return.
            name: Human-readable name.
            available: Whether the backend is available.
            models: List of valid model names.
        """
        self._backend_type = backend_type
        self._name = name
        self._available = available
        # Explicitly handle None vs empty list
        if models is None:
            self._models = ["mock-model-1", "mock-model-2"]
        else:
            self._models = models

    @property
    def backend_type(self) -> BackendType:
        """Return the configured backend type."""
        return self._backend_type

    def transcribe(
        self, audio_path: Path | str, options: TranscriptionOptions
    ) -> TranscriptionResult:
        """Return a mock transcription result."""
        if not self._available:
            raise BackendUnavailableError(
                "Mock backend unavailable",
                context={"backend": self._name, "available": False},
            )

        # Return minimal valid result
        return TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=1.0, text="Mock transcription")],
            media_info=MediaInfo(
                duration=1.0,
                format="wav",
                sample_rate=16000,
                channels=1,
            ),
            config_used=options,
            duration_seconds=0.5,
            backend_used=self._backend_type,
        )

    def get_name(self) -> str:
        """Return the configured backend name."""
        return self._name

    def is_available(self) -> bool:
        """Return the configured availability status."""
        return self._available

    def get_model_options(self) -> list[str]:
        """Return the configured model options."""
        return self._models


class TestTranscriptionBackendABC:
    """Test TranscriptionBackend abstract base class behavior."""

    def test_cannot_instantiate_abstract_class_directly(self) -> None:
        """Verify TranscriptionBackend cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            TranscriptionBackend()  # type: ignore[abstract]

        # Error message should mention abstract methods
        assert "abstract" in str(exc_info.value).lower()

    def test_incomplete_subclass_raises_typeerror(self) -> None:
        """Verify subclass missing methods cannot be instantiated."""

        class IncompleteBackend(TranscriptionBackend):
            """Missing transcribe() and other methods."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

        with pytest.raises(TypeError) as exc_info:
            IncompleteBackend()  # type: ignore[abstract]

        # Error should mention missing abstract methods
        error_msg = str(exc_info.value)
        assert "abstract" in error_msg.lower()

    def test_subclass_missing_transcribe_raises_typeerror(self) -> None:
        """Verify subclass missing transcribe() cannot be instantiated."""

        class MissingTranscribe(TranscriptionBackend):
            """Missing transcribe method."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

            def get_name(self) -> str:
                return "Missing Transcribe"

            def is_available(self) -> bool:
                return True

            def get_model_options(self) -> list[str]:
                return ["model-1"]

        with pytest.raises(TypeError):
            MissingTranscribe()  # type: ignore[abstract]

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """Verify complete subclass can be instantiated."""
        backend = MockTranscriptionBackend()

        assert backend is not None
        assert isinstance(backend, TranscriptionBackend)

    def test_inheritance_chain_works_correctly(self) -> None:
        """Verify inheritance and isinstance checks work."""
        backend = MockTranscriptionBackend()

        assert isinstance(backend, TranscriptionBackend)
        assert hasattr(backend, "backend_type")
        assert hasattr(backend, "transcribe")
        assert hasattr(backend, "get_name")
        assert hasattr(backend, "is_available")
        assert hasattr(backend, "get_model_options")


class TestBackendTypeProperty:
    """Test backend_type property behavior."""

    def test_backend_type_returns_correct_enum(self) -> None:
        """Verify backend_type returns correct BackendType."""
        backend = MockTranscriptionBackend(backend_type=BackendType.OPENAI)
        assert backend.backend_type == BackendType.OPENAI

    def test_backend_type_returns_faster_whisper(self) -> None:
        """Verify backend_type can return faster_whisper."""
        backend = MockTranscriptionBackend(backend_type=BackendType.FASTER_WHISPER)
        assert backend.backend_type == BackendType.FASTER_WHISPER

    def test_backend_type_returns_auto(self) -> None:
        """Verify backend_type can return auto."""
        backend = MockTranscriptionBackend(backend_type=BackendType.AUTO)
        assert backend.backend_type == BackendType.AUTO

    def test_backend_type_is_property(self) -> None:
        """Verify backend_type is a property (not a method)."""
        # Properties are accessed without ()
        backend = MockTranscriptionBackend()
        # Should not raise - accessing as property
        result = backend.backend_type
        assert result == BackendType.OPENAI


class TestGetName:
    """Test get_name() method behavior."""

    def test_get_name_returns_string(self) -> None:
        """Verify get_name returns a string."""
        backend = MockTranscriptionBackend()
        name = backend.get_name()

        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_name_returns_configured_name(self) -> None:
        """Verify get_name returns the configured name."""
        backend = MockTranscriptionBackend(name="Custom Backend")
        assert backend.get_name() == "Custom Backend"

    def test_get_name_different_for_different_backends(self) -> None:
        """Verify different backends can have different names."""
        backend1 = MockTranscriptionBackend(name="Backend One")
        backend2 = MockTranscriptionBackend(name="Backend Two")

        assert backend1.get_name() != backend2.get_name()


class TestIsAvailable:
    """Test is_available() method behavior."""

    def test_is_available_returns_boolean(self) -> None:
        """Verify is_available returns a boolean."""
        backend = MockTranscriptionBackend()
        result = backend.is_available()

        assert isinstance(result, bool)

    def test_is_available_returns_true_when_available(self) -> None:
        """Verify is_available returns True when configured available."""
        backend = MockTranscriptionBackend(available=True)
        assert backend.is_available() is True

    def test_is_available_returns_false_when_unavailable(self) -> None:
        """Verify is_available returns False when configured unavailable."""
        backend = MockTranscriptionBackend(available=False)
        assert backend.is_available() is False

    def test_is_available_can_vary_between_instances(self) -> None:
        """Verify availability can differ between backend instances."""
        available_backend = MockTranscriptionBackend(available=True)
        unavailable_backend = MockTranscriptionBackend(available=False)

        assert available_backend.is_available() is True
        assert unavailable_backend.is_available() is False


class TestGetModelOptions:
    """Test get_model_options() method behavior."""

    def test_get_model_options_returns_list(self) -> None:
        """Verify get_model_options returns a list."""
        backend = MockTranscriptionBackend()
        models = backend.get_model_options()

        assert isinstance(models, list)

    def test_get_model_options_returns_list_of_strings(self) -> None:
        """Verify model options are strings."""
        backend = MockTranscriptionBackend()
        models = backend.get_model_options()

        for model in models:
            assert isinstance(model, str)

    def test_get_model_options_returns_configured_models(self) -> None:
        """Verify get_model_options returns configured models."""
        backend = MockTranscriptionBackend(models=["model-a", "model-b", "model-c"])
        models = backend.get_model_options()

        assert models == ["model-a", "model-b", "model-c"]

    def test_get_model_options_can_be_empty(self) -> None:
        """Verify model list can be empty."""
        backend = MockTranscriptionBackend(models=[])
        models = backend.get_model_options()

        assert models == []

    def test_get_model_options_default_values(self) -> None:
        """Verify default model options exist."""
        backend = MockTranscriptionBackend()
        models = backend.get_model_options()

        assert len(models) >= 1


class TestTranscribeMethodSignature:
    """Test transcribe() method signature and return type."""

    def test_transcribe_accepts_path_object(self) -> None:
        """Verify transcribe accepts Path objects."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions()
        path = Path("/mock/audio.wav")

        # Should not raise - accepts Path
        result = backend.transcribe(path, options)
        assert isinstance(result, TranscriptionResult)

    def test_transcribe_accepts_string_path(self) -> None:
        """Verify transcribe accepts string paths."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions()

        # Should not raise - accepts string
        result = backend.transcribe("/mock/audio.wav", options)
        assert isinstance(result, TranscriptionResult)

    def test_transcribe_accepts_transcription_options(self) -> None:
        """Verify transcribe accepts TranscriptionOptions."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions(language="en")

        result = backend.transcribe("/mock/audio.wav", options)
        assert isinstance(result, TranscriptionResult)

    def test_transcribe_returns_transcription_result(self) -> None:
        """Verify transcribe returns TranscriptionResult."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions()

        result = backend.transcribe("/mock/audio.wav", options)

        assert isinstance(result, TranscriptionResult)
        assert hasattr(result, "segments")
        assert hasattr(result, "media_info")
        assert hasattr(result, "config_used")
        assert hasattr(result, "duration_seconds")
        assert hasattr(result, "backend_used")

    def test_transcribe_result_has_segments(self) -> None:
        """Verify transcribe result includes segments."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions()

        result = backend.transcribe("/mock/audio.wav", options)

        assert isinstance(result.segments, list)
        assert len(result.segments) >= 0

    def test_transcribe_result_has_media_info(self) -> None:
        """Verify transcribe result includes media info."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions()

        result = backend.transcribe("/mock/audio.wav", options)

        assert isinstance(result.media_info, MediaInfo)
        assert result.media_info.duration > 0

    def test_transcribe_preserves_options(self) -> None:
        """Verify transcribe result preserves config_used."""
        backend = MockTranscriptionBackend()
        options = TranscriptionOptions(language="es")

        result = backend.transcribe("/mock/audio.wav", options)

        assert result.config_used.language == "es"


class TestIsBackendAvailableHelper:
    """Test is_backend_available() helper function."""

    def test_returns_true_for_available_backend(self) -> None:
        """Verify helper returns True for available backend."""
        backend = MockTranscriptionBackend(available=True)

        result = is_backend_available(backend)

        assert result is True

    def test_returns_false_for_unavailable_backend(self) -> None:
        """Verify helper returns False for unavailable backend."""
        backend = MockTranscriptionBackend(available=False)

        result = is_backend_available(backend)

        assert result is False

    def test_returns_false_on_exception(self) -> None:
        """Verify helper returns False when is_available() raises."""

        class ErrorBackend(TranscriptionBackend):
            """Backend that raises on is_available."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

            def transcribe(
                self, audio_path: Path | str, options: TranscriptionOptions
            ) -> TranscriptionResult:
                return TranscriptionResult(
                    segments=[],
                    media_info=MediaInfo(
                        duration=1.0,
                        format="wav",
                        sample_rate=16000,
                        channels=1,
                    ),
                    config_used=options,
                    duration_seconds=0.0,
                    backend_used=self.backend_type,
                )

            def get_name(self) -> str:
                return "Error Backend"

            def is_available(self) -> bool:
                raise RuntimeError("Unexpected error in is_available")

            def get_model_options(self) -> list[str]:
                return []

        backend = ErrorBackend()
        result = is_backend_available(backend)

        assert result is False

    def test_logs_warning_on_exception(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify helper logs warning when is_available() raises."""
        # Set log level to capture warnings
        caplog.set_level(logging.WARNING)

        class ErrorBackend(TranscriptionBackend):
            """Backend that raises on is_available."""

            @property
            def backend_type(self) -> BackendType:
                return BackendType.OPENAI

            def transcribe(
                self, audio_path: Path | str, options: TranscriptionOptions
            ) -> TranscriptionResult:
                return TranscriptionResult(
                    segments=[],
                    media_info=MediaInfo(
                        duration=1.0,
                        format="wav",
                        sample_rate=16000,
                        channels=1,
                    ),
                    config_used=options,
                    duration_seconds=0.0,
                    backend_used=self.backend_type,
                )

            def get_name(self) -> str:
                return "Error Backend"

            def is_available(self) -> bool:
                raise RuntimeError("Unexpected error in is_available")

            def get_model_options(self) -> list[str]:
                return []

        backend = ErrorBackend()
        is_backend_available(backend)

        # Check that warning was logged
        assert len(caplog.records) >= 1
        assert any("Exception checking availability" in record.message for record in caplog.records)

    def test_helper_type_hints(self) -> None:
        """Verify helper function type hints are correct."""
        # This test verifies the function signature is correct
        # Type checking is done by mypy/pyright
        backend = MockTranscriptionBackend()
        result: bool = is_backend_available(backend)
        assert isinstance(result, bool)


class TestBackendUnavailableErrorHandling:
    """Test that backends properly raise BackendUnavailableError."""

    def test_transcribe_raises_backend_unavailable_error_when_not_available(self) -> None:
        """Verify transcribe raises BackendUnavailableError when unavailable."""
        backend = MockTranscriptionBackend(available=False)
        options = TranscriptionOptions()

        with pytest.raises(BackendUnavailableError) as exc_info:
            backend.transcribe(Path("/mock/audio.wav"), options)

        assert exc_info.value.error_code == "AUD-201"
        assert "unavailable" in str(exc_info.value).lower()

    def test_unavailable_error_has_context(self) -> None:
        """Verify BackendUnavailableError includes context."""
        backend = MockTranscriptionBackend(available=False)
        options = TranscriptionOptions()

        with pytest.raises(BackendUnavailableError) as exc_info:
            backend.transcribe("/mock/audio.wav", options)

        assert exc_info.value.context is not None
        assert "backend" in exc_info.value.context


class TestMultipleBackends:
    """Test behavior with multiple backend implementations."""

    def test_multiple_backends_independent(self) -> None:
        """Verify multiple backends can coexist independently."""
        backend1 = MockTranscriptionBackend(
            backend_type=BackendType.OPENAI,
            name="OpenAI Backend",
            available=True,
            models=["whisper-1"],
        )
        backend2 = MockTranscriptionBackend(
            backend_type=BackendType.FASTER_WHISPER,
            name="Faster Whisper Backend",
            available=False,
            models=["small", "medium", "large"],
        )

        # Check backend types
        assert backend1.backend_type == BackendType.OPENAI
        assert backend2.backend_type == BackendType.FASTER_WHISPER

        # Check names
        assert backend1.get_name() != backend2.get_name()

        # Check availability
        assert backend1.is_available() is True
        assert backend2.is_available() is False

        # Check model options
        assert backend1.get_model_options() == ["whisper-1"]
        assert backend2.get_model_options() == ["small", "medium", "large"]

    def test_backends_have_same_interface(self) -> None:
        """Verify all backends share the same interface."""
        backends = [
            MockTranscriptionBackend(backend_type=BackendType.OPENAI),
            MockTranscriptionBackend(backend_type=BackendType.FASTER_WHISPER),
            MockTranscriptionBackend(backend_type=BackendType.AUTO),
        ]

        for backend in backends:
            # All backends must have these methods
            assert hasattr(backend, "backend_type")
            assert hasattr(backend, "transcribe")
            assert hasattr(backend, "get_name")
            assert hasattr(backend, "is_available")
            assert hasattr(backend, "get_model_options")

            # All methods must be callable
            assert callable(backend.transcribe)
            assert callable(backend.get_name)
            assert callable(backend.is_available)
            assert callable(backend.get_model_options)
