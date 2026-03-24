"""Configuration-related exceptions."""

from audiocore.errors.base import AudioCoreError


class ConfigurationError(AudioCoreError):
    """Base exception for configuration-related errors."""

    error_code: str = "AUD-004"


class InvalidConfigError(ConfigurationError):
    """Invalid configuration provided."""

    error_code: str = "AUD-005"
