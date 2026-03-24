"""Tests for input-related exceptions."""

import pytest

from audiocore.errors.base import AudioCoreError
from audiocore.errors.input import (
    InputError,
    InvalidInputError,
    MediaFormatError,
)


class TestInputError:
    """Test InputError base class."""

    def test_inherits_from_audiocore_error(self) -> None:
        """InputError should inherit from AudioCoreError."""
        assert issubclass(InputError, AudioCoreError)

    def test_error_code(self) -> None:
        """InputError should have correct error code."""
        assert InputError.error_code == "AUD-001"

    def test_default_suggestions(self) -> None:
        """InputError should provide default suggestions."""
        error = InputError("Invalid input")
        assert len(error.suggestions) > 0
        assert any("file" in s.lower() for s in error.suggestions)


class TestInvalidInputError:
    """Test InvalidInputError exception."""

    def test_inherits_from_input_error(self) -> None:
        """InvalidInputError should inherit from InputError."""
        assert issubclass(InvalidInputError, InputError)
        assert issubclass(InvalidInputError, AudioCoreError)

    def test_error_code(self) -> None:
        """InvalidInputError should have correct error code."""
        assert InvalidInputError.error_code == "AUD-002"

    def test_initialization_with_context(self) -> None:
        """InvalidInputError should accept context dictionary."""
        context = {"file_path": "/path/to/file.mp3"}
        error = InvalidInputError("File not found", context=context)
        assert error.context == context

    def test_default_suggestions(self) -> None:
        """InvalidInputError should provide helpful default suggestions."""
        error = InvalidInputError("Invalid input")
        assert len(error.suggestions) >= 3
        assert any("path" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Custom suggestion 1", "Custom suggestion 2"]
        error = InvalidInputError("Error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_str_representation_with_context(self) -> None:
        """String representation should include context."""
        error = InvalidInputError(
            "File not found",
            context={"file": "test.mp3", "cwd": "/home/user"},
        )
        result = str(error)
        assert "File not found" in result
        assert "file=" in result
        assert "test.mp3" in result


class TestMediaFormatError:
    """Test MediaFormatError exception."""

    def test_inherits_from_input_error(self) -> None:
        """MediaFormatError should inherit from InputError."""
        assert issubclass(MediaFormatError, InputError)
        assert issubclass(MediaFormatError, AudioCoreError)

    def test_error_code(self) -> None:
        """MediaFormatError should have correct error code."""
        assert MediaFormatError.error_code == "AUD-003"

    def test_initialization_with_format_context(self) -> None:
        """MediaFormatError should accept format context."""
        context = {
            "file_path": "video.mkv",
            "format": "matroska",
            "codec": "h265",
        }
        error = MediaFormatError("Unsupported format", context=context)
        assert error.context == context

    def test_default_suggestions_for_format_issues(self) -> None:
        """MediaFormatError should provide format-specific suggestions."""
        error = MediaFormatError("Unsupported format")
        assert len(error.suggestions) >= 3
        assert any("format" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Convert to MP4", "Use ffmpeg"]
        error = MediaFormatError("Error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_output(self) -> None:
        """format_error should produce formatted output."""
        error = MediaFormatError(
            "Unsupported format",
            context={"file": "video.mkv"},
            suggestions=["Convert to mp3", "Install codec"],
        )
        result = error.format_error()
        assert "[AUD-003] Unsupported format" in result
        assert "Context:" in result
        assert "file: video.mkv" in result
        assert "1. Convert to mp3" in result


class TestInputExceptionHierarchy:
    """Test the input exception inheritance hierarchy."""

    def test_exception_chaining_from_io_error(self) -> None:
        """InvalidInputError should chain from IOError."""
        try:
            # Simulate file not found
            raise FileNotFoundError("No such file")
        except FileNotFoundError as e:
            error = InvalidInputError(
                "Audio file not found",
                context={"file": "missing.mp3"},
                cause=e,
            )
            assert error.message == "Audio file not found"
            assert error.context["file"] == "missing.mp3"

    def test_unique_error_codes(self) -> None:
        """Each exception class should have unique error code."""
        codes = [InputError.error_code, InvalidInputError.error_code, MediaFormatError.error_code]
        assert len(set(codes)) == len(codes)  # All codes should be unique
