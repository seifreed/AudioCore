"""API-related exceptions."""

from audiocore.errors.base import AudioCoreError


class APIError(AudioCoreError):
    """Base exception for API-related errors."""

    error_code: str = "AUD-009"


class AuthenticationError(APIError):
    """Authentication failed."""

    error_code: str = "AUD-010"


class RateLimitError(APIError):
    """Rate limit exceeded."""

    error_code: str = "AUD-011"


class APITimeoutError(APIError):
    """API request timed out."""

    error_code: str = "AUD-012"
