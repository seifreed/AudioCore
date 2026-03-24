"""
Configuration-related exceptions.

These exceptions are raised when there are problems with configuration,
such as invalid settings or missing configuration files.
"""

from typing import Any

from audiocore.errors.base import AudioCoreError


class ConfigurationError(AudioCoreError):
    """
    Base exception for configuration-related errors.

    Inherit from this for exceptions related to settings,
    environment variables, and configuration files.
    """

    error_code: str = "AUD-100"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        if suggestions is None:
            suggestions = [
                "Check configuration file syntax",
                "Verify environment variables",
                "Refer to documentation for valid options",
            ]
        super().__init__(message, context, suggestions, cause)


class InvalidConfigError(ConfigurationError):
    """
    Exception raised when configuration is invalid.

    This includes:
    - Invalid configuration value
    - Missing required configuration
    - Configuration type mismatch

    Example:
        >>> raise InvalidConfigError(
        ...     "Invalid backend selection",
        ...     context={
        ...         "key": "AUDIOCORE_BACKEND",
        ...         "value": "invalid_backend",
        ...         "valid_values": ["openai", "faster_whisper", "auto"],
        ...     },
        ...     suggestions=["Set AUDIOCORE_BACKEND to one of: openai, faster_whisper, auto"]
        ... )
    """

    error_code: str = "AUD-101"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Add default suggestions if none provided
        if suggestions is None:
            suggestions = [
                "Check configuration file syntax",
                "Verify configuration value type",
                "Refer to documentation for valid options",
            ]
        super().__init__(message, context, suggestions, cause)
