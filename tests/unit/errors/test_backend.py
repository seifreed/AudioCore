"""Tests for backend-related exceptions."""

import pytest

from audiocore.errors.base import AudioCoreError
from audiocore.errors.backend import (
    BackendError,
    BackendUnavailableError,
    TranscriptionError,
)


class TestBackendError:
    """Test BackendError base class."""

    def test_inherits_from_audiocore_error(self) -> None:
        """BackendError should inherit from AudioCoreError."""
        assert issubclass(BackendError, AudioCoreError)

    def test_error_code(self) -> None:
        """BackendError should have correct error code."""
        assert BackendError.error_code == "AUD-200"

    def test_default_suggestions(self) -> None:
        """BackendError should provide default suggestions."""
        error = BackendError("Backend error")
        assert len(error.suggestions) > 0
        assert any("backend" in s.lower() for s in error.suggestions)


class TestBackendUnavailableError:
    """Test BackendUnavailableError exception."""

    def test_inherits_from_backend_error(self) -> None:
        """BackendUnavailableError should inherit from BackendError."""
        assert issubclass(BackendUnavailableError, BackendError)
        assert issubclass(BackendUnavailableError, AudioCoreError)

    def test_error_code(self) -> None:
        """BackendUnavailableError should have correct error code."""
        assert BackendUnavailableError.error_code == "AUD-201"

    def test_initialization_with_backend_context(self) -> None:
        """BackendUnavailableError should accept backend context."""
        context = {
            "backend": "openai",
            "reason": "API key not configured",
        }
        error = BackendUnavailableError("OpenAI unavailable", context=context)
        assert error.context == context

    def test_default_suggestions_for_unavailable(self) -> None:
        """BackendUnavailableError should provide availability suggestions."""
        error = BackendUnavailableError("Backend unavailable")
        assert len(error.suggestions) >= 3
        assert any("install" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Install faster-whisper", "Use OpenAI"]
        error = BackendUnavailableError("Error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_api_key_error_context(self) -> None:
        """BackendUnavailableError should handle API key context."""
        error = BackendUnavailableError(
            "API key not configured",
            context={"backend": "openai", "env_var": "AUDIOCORE_OPENAI_API_KEY"},
            suggestions=["Set AUDIOCORE_OPENAI_API_KEY"],
        )
        result = error.format_error()
        assert "[AUD-201] API key not configured" in result
        assert "env_var: AUDIOCORE_OPENAI_API_KEY" in result


class TestTranscriptionError:
    """Test TranscriptionError exception."""

    def test_inherits_from_backend_error(self) -> None:
        """TranscriptionError should inherit from BackendError."""
        assert issubclass(TranscriptionError, BackendError)
        assert issubclass(TranscriptionError, AudioCoreError)

    def test_error_code(self) -> None:
        """TranscriptionError should have correct error code."""
        assert TranscriptionError.error_code == "AUD-202"

    def test_initialization_with_transcription_context(self) -> None:
        """TranscriptionError should accept transcription context."""
        context = {
            "backend": "faster_whisper",
            "model": "large-v3",
            "file": "long_audio.mp3",
        }
        error = TranscriptionError("Transcription failed", context=context)
        assert error.context == context

    def test_default_suggestions(self) -> None:
        """TranscriptionError should provide transcription suggestions."""
        error = TranscriptionError("Transcription error")
        assert len(error.suggestions) >= 3
        assert any("format" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Try smaller model", "Check memory"]
        error = TranscriptionError("Error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_with_model_info(self) -> None:
        """format_error should include model information."""
        error = TranscriptionError(
            "Transcription failed",
            context={"backend": "faster_whisper", "model": "large-v3"},
            suggestions=["Try smaller model size"],
        )
        result = error.format_error()
        assert "[AUD-202] Transcription failed" in result
        assert "model: large-v3" in result


class TestBackendExceptionHierarchy:
    """Test backend exception inheritance."""

    def test_unique_error_codes(self) -> None:
        """Each backend exception should have unique error code."""
        codes = [
            BackendError.error_code,
            BackendUnavailableError.error_code,
            TranscriptionError.error_code,
        ]
        assert len(set(codes)) == len(codes)

    def test_exception_str_representation(self) -> None:
        """Exception string should be informative."""
        error = TranscriptionError(
            "Model failed to load",
            context={"model": "large-v3", "error": "OOM"},
        )
        result = str(error)
        assert "Model failed to load" in result
        assert "model=" in result
        assert "large-v3" in result
