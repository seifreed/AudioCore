"""Tests for processing-related exceptions."""

import pytest

from audiocore.errors.base import AudioCoreError
from audiocore.errors.processing import (
    ProcessingError,
    VADError,
)


class TestProcessingError:
    """Test ProcessingError base class."""

    def test_inherits_from_audiocore_error(self) -> None:
        """ProcessingError should inherit from AudioCoreError."""
        assert issubclass(ProcessingError, AudioCoreError)

    def test_error_code(self) -> None:
        """ProcessingError should have correct error code."""
        assert ProcessingError.error_code == "AUD-400"

    def test_default_suggestions(self) -> None:
        """ProcessingError should provide default suggestions."""
        error = ProcessingError("Processing error")
        assert len(error.suggestions) > 0
        assert any("check" in s.lower() or "try" in s.lower() for s in error.suggestions)


class TestVADError:
    """Test VADError exception."""

    def test_inherits_from_processing_error(self) -> None:
        """VADError should inherit from ProcessingError."""
        assert issubclass(VADError, ProcessingError)
        assert issubclass(VADError, AudioCoreError)

    def test_error_code(self) -> None:
        """VADError should have correct error code."""
        assert VADError.error_code == "AUD-401"

    def test_initialization_with_vad_context(self) -> None:
        """VADError should accept VAD-specific context."""
        context = {
            "model": "silero_vad",
            "reason": "Model load failed",
            "audio_duration": 3600,
        }
        error = VADError("VAD processing failed", context=context)
        assert error.context == context

    def test_default_suggestions(self) -> None:
        """VADError should provide VAD-related suggestions."""
        error = VADError("VAD error")
        assert len(error.suggestions) >= 3
        assert any("vad" in s.lower() or "model" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Download model again", "Check memory"]
        error = VADError("VAD error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_with_model_info(self) -> None:
        """format_error should include model information."""
        error = VADError(
            "Failed to load VAD model",
            context={"model": "silero_vad", "source": "torch_hub"},
            suggestions=["Check internet connection", "Use cached model"],
        )
        result = error.format_error()
        assert "[AUD-401] Failed to load VAD model" in result
        assert "model: silero_vad" in result
        assert "source: torch_hub" in result

    def test_initialization_with_memory_context(self) -> None:
        """VADError should accept memory-related context."""
        context = {
            "error": "Out of memory",
            "audio_duration": 7200,
            "available_memory": "512MB",
        }
        error = VADError("Memory exhausted during VAD", context=context)
        assert error.context == context


class TestProcessingExceptionHierarchy:
    """Test processing exception inheritance."""

    def test_unique_error_codes(self) -> None:
        """Each processing exception should have unique error code."""
        codes = [ProcessingError.error_code, VADError.error_code]
        assert len(set(codes)) == len(codes)

    def test_exception_str_representation(self) -> None:
        """Exception string should be informative."""
        error = VADError(
            "VAD model failed to initialize",
            context={"model": "silero_vad", "device": "cuda"},
        )
        result = str(error)
        assert "VAD model failed to initialize" in result
        assert "model=" in result
        assert "silero_vad" in result

    def test_exception_can_wrap_original_error(self) -> None:
        """VADError should be able to wrap original exceptions."""
        try:
            # Simulate underlying error
            raise RuntimeError("CUDA out of memory")
        except RuntimeError as original:
            error = VADError(
                "VAD processing failed",
                context={"model": "silero_vad", "gpu_memory": "insufficient"},
                suggestions=["Use CPU device", "Process shorter segments"],
            )
            error.__cause__ = original
            error.__context__ = original.__context__ if hasattr(original, "__context__") else None
            
            # Verify cause is preserved
            assert error.__cause__ is original

    def test_exception_with_chaining(self) -> None:
        """VADError should work with exception chaining."""
        try:
            # Simulate error chain
            try:
                raise ValueError("Invalid audio format")
            except ValueError as inner:
                raise VADError(
                    "VAD cannot process format",
                    context={"format": "xyz"},
                    cause=inner,
                ) from inner
        except VADError as e:
            # Verify chaining worked
            assert isinstance(e.__cause__, ValueError)
