"""
API-related exceptions.

These exceptions are raised when there are problems with external API
calls such as authentication, rate limiting, or timeouts.
"""

from typing import Any

from audiocore.errors.base import AudioCoreError


class APIError(AudioCoreError):
    """
    Base exception for API-related errors.

    Inherit from this for exceptions related to external API calls,
    authentication, rate limiting, and network issues.
    """

    error_code: str = "AUD-300"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check API service status",
                "Verify network connectivity",
                "Retry request after delay",
            ]
        super().__init__(message, context, suggestions, cause)


class AuthenticationError(APIError):
    """
    Exception raised when API authentication fails.

    This is raised when:
    - API key is invalid or expired
    - API key is missing
    - Authentication headers are incorrect

    Example:
        >>> raise AuthenticationError(
        ...     "OpenAI API key is invalid",
        ...     context={"provider": "openai"},
        ...     suggestions=[
        ...         "Verify API key at https://platform.openai.com/api-keys",
        ...         "Set AUDIOCORE_OPENAI_API_KEY environment variable",
        ...         "Check API key has not expired",
        ...     ]
        ... )
    """

    error_code: str = "AUD-301"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Verify API key is correct",
                "Check API key has not expired",
                "Ensure API key has required permissions",
            ]
        super().__init__(message, context, suggestions, cause)


class RateLimitError(APIError):
    """
    Exception raised when API rate limit is exceeded.

    This includes:
    - Request rate limit exceeded
    - Token rate limit exceeded
    - Quota exceeded

    Example:
        >>> raise RateLimitError(
        ...     "OpenAI rate limit exceeded",
        ...     context={
        ...         "provider": "openai",
        ...         "retry_after": 30,
        ...     },
        ...     suggestions=[
        ...         f"Wait 30 seconds before retrying",
        ...         "Consider upgrading API tier",
        ...         "Implement request throttling",
        ...     ]
        ... )
    """

    error_code: str = "AUD-302"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = ["Wait before retrying", "Reduce request frequency"]
        # Add retry_after context to suggestions if available
        if context and "retry_after" in context:
            retry_after = context["retry_after"]
            if suggestions is None:
                suggestions = []
            suggestions = [f"Wait {retry_after} seconds before retrying"] + suggestions
        super().__init__(message, context, suggestions, cause)


class APITimeoutError(APIError):
    """
    Exception raised when API request times out.

    This is raised when:
    - Request takes too long
    - Server does not respond
    - Network timeout occurs

    Example:
        >>> raise APITimeoutError(
        ...     "OpenAI API request timed out",
        ...     context={
        ...         "provider": "openai",
        ...         "timeout_seconds": 30,
        ...         "operation": "transcription",
        ...     },
        ...     suggestions=[
        ...         "Retry with shorter audio file",
        ...         "Increase timeout configuration",
        ...         "Check network stability",
        ...     ]
        ... )
    """

    error_code: str = "AUD-303"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Retry request",
                "Check network connection",
                "Consider using shorter audio segments",
            ]
        super().__init__(message, context, suggestions, cause)
