"""Tests for AudioCoreError base class."""


from audiocore.errors.base import AudioCoreError


class TestAudioCoreError:
    """Test AudioCoreError base exception functionality."""

    def test_error_code_class_attribute(self) -> None:
        """AudioCoreError should have default error code."""
        assert hasattr(AudioCoreError, "error_code")
        assert AudioCoreError.error_code == "AUD-000"

    def test_message_initialization(self) -> None:
        """AudioCoreError should store message."""
        error = AudioCoreError("Test error message")
        assert error.message == "Test error message"

    def test_context_initialization(self) -> None:
        """AudioCoreError should store context dictionary."""
        context = {"file": "test.mp3", "operation": "transcribe"}
        error = AudioCoreError("Test error", context=context)
        assert error.context == context

    def test_context_defaults_to_empty_dict(self) -> None:
        """AudioCoreError context should default to empty dict."""
        error = AudioCoreError("Test error")
        assert error.context == {}

    def test_suggestions_initialization(self) -> None:
        """AudioCoreError should store suggestions list."""
        suggestions = ["Try this", "Or try that"]
        error = AudioCoreError("Test error", suggestions=suggestions)
        assert error.suggestions == suggestions

    def test_suggestions_defaults_to_empty_list(self) -> None:
        """AudioCoreError suggestions should default to empty list."""
        error = AudioCoreError("Test error")
        assert error.suggestions == []

    def test_str_without_context(self) -> None:
        """String representation without context should be message only."""
        error = AudioCoreError("Test error")
        assert str(error) == "Test error"

    def test_str_with_context(self) -> None:
        """String representation with context should include key-value pairs."""
        error = AudioCoreError("Test error", context={"file": "test.mp3", "line": 42})
        result = str(error)
        assert "Test error" in result
        assert "file=" in result
        assert "test.mp3" in result

    def test_repr(self) -> None:
        """Repr should include all attributes."""
        error = AudioCoreError(
            "Test error",
            context={"key": "value"},
            suggestions=["Try this"],
        )
        result = repr(error)
        assert "AudioCoreError" in result
        assert "message=" in result
        assert "error_code=" in result
        assert "context=" in result
        assert "suggestions=" in result

    def test_format_error_without_context(self) -> None:
        """format_error should return formatted message without context."""
        error = AudioCoreError("Test error")
        result = error.format_error()
        assert "[AUD-000] Test error" in result

    def test_format_error_with_context(self) -> None:
        """format_error should include context in output."""
        error = AudioCoreError(
            "Test error",
            context={"file": "test.mp3", "operation": "transcribe"},
        )
        result = error.format_error()
        assert "[AUD-000] Test error" in result
        assert "Context:" in result
        assert "file: test.mp3" in result

    def test_format_error_with_suggestions(self) -> None:
        """format_error should include numbered suggestions."""
        suggestions = ["Check file", "Try again"]
        error = AudioCoreError("Test error", suggestions=suggestions)
        result = error.format_error()
        assert "Suggestions:" in result
        assert "1. Check file" in result
        assert "2. Try again" in result

    def test_format_error_complete(self) -> None:
        """format_error should combine all elements."""
        error = AudioCoreError(
            "Something went wrong",
            context={"file": "audio.mp3"},
            suggestions=["Check format", "Try different file"],
        )
        result = error.format_error()
        lines = result.split("\n")
        assert "[AUD-000] Something went wrong" in lines[0]
        assert "Context:" in result
        assert "file: audio.mp3" in result
        assert "Suggestions:" in result
        assert "1. Check format" in result
        assert "2. Try different file" in result

    def test_exception_chaining(self) -> None:
        """AudioCoreError should preserve original exception via __cause__."""
        original = ValueError("Original error")
        try:
            raise AudioCoreError("Wrapped error", cause=original) from original
        except AudioCoreError as e:
            assert e.__cause__ is original
            assert isinstance(e.__cause__, ValueError)
