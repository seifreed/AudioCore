"""Tests for configuration-related exceptions."""


from audiocore.errors.base import AudioCoreError
from audiocore.errors.config import (
    ConfigurationError,
    InvalidConfigError,
)


class TestConfigurationError:
    """Test ConfigurationError base class."""

    def test_inherits_from_audiocore_error(self) -> None:
        """ConfigurationError should inherit from AudioCoreError."""
        assert issubclass(ConfigurationError, AudioCoreError)

    def test_error_code(self) -> None:
        """ConfigurationError should have correct error code."""
        assert ConfigurationError.error_code == "AUD-100"

    def test_default_suggestions(self) -> None:
        """ConfigurationError should provide default suggestions."""
        error = ConfigurationError("Config error")
        assert len(error.suggestions) > 0
        assert any("config" in s.lower() for s in error.suggestions)


class TestInvalidConfigError:
    """Test InvalidConfigError exception."""

    def test_inherits_from_configuration_error(self) -> None:
        """InvalidConfigError should inherit from ConfigurationError."""
        assert issubclass(InvalidConfigError, ConfigurationError)
        assert issubclass(InvalidConfigError, AudioCoreError)

    def test_error_code(self) -> None:
        """InvalidConfigError should have correct error code."""
        assert InvalidConfigError.error_code == "AUD-101"

    def test_initialization_with_config_context(self) -> None:
        """InvalidConfigError should accept configuration context."""
        context = {
            "key": "AUDIOCORE_BACKEND",
            "value": "invalid_backend",
            "valid_values": ["openai", "faster_whisper", "auto"],
        }
        error = InvalidConfigError("Invalid backend", context=context)
        assert error.context == context

    def test_default_suggestions(self) -> None:
        """InvalidConfigError should provide helpful default suggestions."""
        error = InvalidConfigError("Invalid config")
        assert len(error.suggestions) >= 3
        assert any("syntax" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Set to 'openai'", "Set to 'faster_whisper'"]
        error = InvalidConfigError("Error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_with_invalid_config(self) -> None:
        """format_error should format configuration errors properly."""
        error = InvalidConfigError(
            "Invalid backend selection",
            context={
                "key": "AUDIOCORE_BACKEND",
                "value": "unknown",
            },
            suggestions=["Set to 'openai'", "Set to 'faster_whisper'"],
        )
        result = error.format_error()
        assert "[AUD-101] Invalid backend selection" in result
        assert "Context:" in result
        assert "key: AUDIOCORE_BACKEND" in result
        assert "value: unknown" in result
        assert "1. Set to 'openai'" in result


class TestConfigExceptionHierarchy:
    """Test configuration exception inheritance."""

    def test_unique_error_codes(self) -> None:
        """Each config exception should have unique error code."""
        codes = [ConfigurationError.error_code, InvalidConfigError.error_code]
        assert len(set(codes)) == len(codes)

    def test_exception_str_representation(self) -> None:
        """Exception string should be informative."""
        error = InvalidConfigError(
            "Missing required config",
            context={"missing_key": "AUDIOCORE_OPENAI_API_KEY"},
        )
        result = str(error)
        assert "Missing required config" in result
        assert "missing_key" in result
