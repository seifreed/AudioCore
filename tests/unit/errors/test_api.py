"""Tests for API-related exceptions."""

import pytest

from audiocore.errors.base import AudioCoreError
from audiocore.errors.api import (
    APIError,
    AuthenticationError,
    RateLimitError,
    APITimeoutError,
)


class TestAPIError:
    """Test APIError base class."""

    def test_inherits_from_audiocore_error(self) -> None:
        """APIError should inherit from AudioCoreError."""
        assert issubclass(APIError, AudioCoreError)

    def test_error_code(self) -> None:
        """APIError should have correct error code."""
        assert APIError.error_code == "AUD-300"

    def test_default_suggestions(self) -> None:
        """APIError should provide default suggestions."""
        error = APIError("API error")
        assert len(error.suggestions) > 0
        assert any("api" in s.lower() or "retry" in s.lower() for s in error.suggestions)


class TestAuthenticationError:
    """Test AuthenticationError exception."""

    def test_inherits_from_api_error(self) -> None:
        """AuthenticationError should inherit from APIError."""
        assert issubclass(AuthenticationError, APIError)
        assert issubclass(AuthenticationError, AudioCoreError)

    def test_error_code(self) -> None:
        """AuthenticationError should have correct error code."""
        assert AuthenticationError.error_code == "AUD-301"

    def test_initialization_with_provider_context(self) -> None:
        """AuthenticationError should accept provider context."""
        context = {"provider": "openai"}
        error = AuthenticationError("Invalid API key", context=context)
        assert error.context == context

    def test_default_suggestions(self) -> None:
        """AuthenticationError should provide auth suggestions."""
        error = AuthenticationError("Auth failed")
        assert len(error.suggestions) >= 3
        assert any("key" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Check API key", "Verify permissions"]
        error = AuthenticationError("Auth error", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_with_provider(self) -> None:
        """format_error should include provider information."""
        error = AuthenticationError(
            "API key is invalid",
            context={"provider": "openai", "key_prefix": "sk-..."},
            suggestions=["Verify API key at platform.openai.com"],
        )
        result = error.format_error()
        assert "[AUD-301] API key is invalid" in result
        assert "provider: openai" in result


class TestRateLimitError:
    """Test RateLimitError exception."""

    def test_inherits_from_api_error(self) -> None:
        """RateLimitError should inherit from APIError."""
        assert issubclass(RateLimitError, APIError)
        assert issubclass(RateLimitError, AudioCoreError)

    def test_error_code(self) -> None:
        """RateLimitError should have correct error code."""
        assert RateLimitError.error_code == "AUD-302"

    def test_initialization_with_rate_limit_context(self) -> None:
        """RateLimitError should accept rate limit context."""
        context = {"provider": "openai", "retry_after": 30}
        error = RateLimitError("Rate limit exceeded", context=context)
        assert error.context == context

    def test_suggestions_include_retry_after(self) -> None:
        """RateLimitError suggestions should include retry_after when present."""
        context = {"retry_after": 30}
        error = RateLimitError("Rate limited", context=context)
        assert any("30" in s for s in error.suggestions)

    def test_suggestions_without_retry_after(self) -> None:
        """RateLimitError should have default suggestions without retry_after."""
        error = RateLimitError("Rate limited")
        assert len(error.suggestions) >= 2
        assert any("retry" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Wait 60 seconds", "Reduce frequency"]
        error = RateLimitError("Rate limited", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_with_retry_after(self) -> None:
        """format_error should include retry_after information."""
        error = RateLimitError(
            "Rate limit exceeded",
            context={"provider": "openai", "retry_after": 45},
        )
        result = error.format_error()
        assert "[AUD-302] Rate limit exceeded" in result
        assert "retry_after: 45" in result


class TestAPITimeoutError:
    """Test APITimeoutError exception."""

    def test_inherits_from_api_error(self) -> None:
        """APITimeoutError should inherit from APIError."""
        assert issubclass(APITimeoutError, APIError)
        assert issubclass(APITimeoutError, AudioCoreError)

    def test_error_code(self) -> None:
        """APITimeoutError should have correct error code."""
        assert APITimeoutError.error_code == "AUD-303"

    def test_initialization_with_timeout_context(self) -> None:
        """APITimeoutError should accept timeout context."""
        context = {
            "provider": "openai",
            "timeout_seconds": 30,
            "operation": "transcription",
        }
        error = APITimeoutError("Request timed out", context=context)
        assert error.context == context

    def test_default_suggestions(self) -> None:
        """APITimeoutError should provide timeout suggestions."""
        error = APITimeoutError("Timeout")
        assert len(error.suggestions) >= 3
        assert any("retry" in s.lower() for s in error.suggestions)

    def test_custom_suggestions_override_defaults(self) -> None:
        """Custom suggestions should override defaults."""
        custom_suggestions = ["Increase timeout", "Use shorter audio"]
        error = APITimeoutError("Timeout", suggestions=custom_suggestions)
        assert error.suggestions == custom_suggestions

    def test_format_error_with_timeout_info(self) -> None:
        """format_error should include timeout information."""
        error = APITimeoutError(
            "Request timed out",
            context={"provider": "openai", "timeout_seconds": 60},
            suggestions=["Increase timeout", "Use shorter segments"],
        )
        result = error.format_error()
        assert "[AUD-303] Request timed out" in result
        assert "timeout_seconds: 60" in result


class TestAPIExceptionHierarchy:
    """Test API exception inheritance."""

    def test_unique_error_codes(self) -> None:
        """Each API exception should have unique error code."""
        codes = [
            APIError.error_code,
            AuthenticationError.error_code,
            RateLimitError.error_code,
            APITimeoutError.error_code,
        ]
        assert len(set(codes)) == len(codes)

    def test_exception_str_representation(self) -> None:
        """Exception string should be informative."""
        error = RateLimitError(
            "Request rate limited",
            context={"provider": "openai", "limit": "3 requests per minute"},
        )
        result = str(error)
        assert "Request rate limited" in result
        assert "provider=" in result
