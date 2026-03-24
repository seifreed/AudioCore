"""Tests for ModelErrorType enum."""

import pytest

from audiocore.types import ModelErrorType


class TestModelErrorType:
    """Tests for ModelErrorType enum."""

    def test_values(self) -> None:
        """Test that ModelErrorType has correct values."""
        assert ModelErrorType.FILE_NOT_FOUND.value == "file_not_found"
        assert ModelErrorType.INVALID_FORMAT.value == "invalid_format"
        assert ModelErrorType.EXTRACTION_FAILED.value == "extraction_failed"
        assert ModelErrorType.VAD_FAILED.value == "vad_failed"
        assert ModelErrorType.VAD_MODEL_LOAD_FAILED.value == "vad_model_load_failed"
        assert ModelErrorType.BACKEND_UNAVAILABLE.value == "backend_unavailable"
        assert ModelErrorType.TRANSCRIPTION_FAILED.value == "transcription_failed"
        assert ModelErrorType.AUTH_FAILED.value == "auth_failed"
        assert ModelErrorType.RATE_LIMITED.value == "rate_limited"
        assert ModelErrorType.API_TIMEOUT.value == "api_timeout"

    def test_str_enum_inheritance(self) -> None:
        """Test that ModelErrorType inherits from str and Enum."""
        assert isinstance(ModelErrorType.RATE_LIMITED, str)
        assert ModelErrorType.RATE_LIMITED == "rate_limited"

    def test_parse_case_insensitive(self) -> None:
        """Test parse() method with various case formats."""
        assert ModelErrorType.parse("file_not_found") == ModelErrorType.FILE_NOT_FOUND
        assert ModelErrorType.parse("FILE_NOT_FOUND") == ModelErrorType.FILE_NOT_FOUND
        assert ModelErrorType.parse("rate_limited") == ModelErrorType.RATE_LIMITED
        assert ModelErrorType.parse("RATE_LIMITED") == ModelErrorType.RATE_LIMITED
        assert ModelErrorType.parse("auth-failed") == ModelErrorType.AUTH_FAILED
        assert ModelErrorType.parse("Auth Failed") == ModelErrorType.AUTH_FAILED

    def test_parse_invalid_value(self) -> None:
        """Test parse() raises ValueError for invalid values."""
        with pytest.raises(ValueError) as exc_info:
            ModelErrorType.parse("unknown_error")

        assert "Invalid error type" in str(exc_info.value)
        # Check that some valid options are listed
        assert "file_not_found" in str(exc_info.value)
        assert "rate_limited" in str(exc_info.value)

    def test_is_input_error(self) -> None:
        """Test is_input_error() method."""
        assert ModelErrorType.FILE_NOT_FOUND.is_input_error() is True
        assert ModelErrorType.INVALID_FORMAT.is_input_error() is True
        assert ModelErrorType.EXTRACTION_FAILED.is_input_error() is True
        assert ModelErrorType.VAD_FAILED.is_input_error() is False
        assert ModelErrorType.RATE_LIMITED.is_input_error() is False

    def test_is_vad_error(self) -> None:
        """Test is_vad_error() method."""
        assert ModelErrorType.VAD_FAILED.is_vad_error() is True
        assert ModelErrorType.VAD_MODEL_LOAD_FAILED.is_vad_error() is True
        assert ModelErrorType.FILE_NOT_FOUND.is_vad_error() is False
        assert ModelErrorType.BACKEND_UNAVAILABLE.is_vad_error() is False

    def test_is_backend_error(self) -> None:
        """Test is_backend_error() method."""
        assert ModelErrorType.BACKEND_UNAVAILABLE.is_backend_error() is True
        assert ModelErrorType.TRANSCRIPTION_FAILED.is_backend_error() is True
        assert ModelErrorType.VAD_FAILED.is_backend_error() is False
        assert ModelErrorType.AUTH_FAILED.is_backend_error() is False

    def test_is_api_error(self) -> None:
        """Test is_api_error() method."""
        assert ModelErrorType.AUTH_FAILED.is_api_error() is True
        assert ModelErrorType.RATE_LIMITED.is_api_error() is True
        assert ModelErrorType.API_TIMEOUT.is_api_error() is True
        assert ModelErrorType.FILE_NOT_FOUND.is_api_error() is False
        assert ModelErrorType.VAD_FAILED.is_api_error() is False

    def test_all_values_exist(self) -> None:
        """Test that all expected values exist."""
        values = [m.value for m in ModelErrorType]
        assert "file_not_found" in values
        assert "invalid_format" in values
        assert "extraction_failed" in values
        assert "vad_failed" in values
        assert "vad_model_load_failed" in values
        assert "backend_unavailable" in values
        assert "transcription_failed" in values
        assert "auth_failed" in values
        assert "rate_limited" in values
        assert "api_timeout" in values
