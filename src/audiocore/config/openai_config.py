"""OpenAI-specific configuration for AudioCore.

This module provides OpenAIConfig for configuring OpenAI Whisper API
parameters including API key security, organization, base URL, and
request settings.

Key Features:
- SecretStr for API key protection
- Configurable timeout and retry settings
- Optional organization and base URL for proxies
"""

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI Whisper API backend.

    Stores OpenAI API credentials and configuration options for the
    OpenAI transcription backend. All sensitive credentials use
    SecretStr to prevent accidental exposure in logs and string
    representations.

    Attributes:
        api_key: OpenAI API key (from OPENAI_API_KEY env var or passed directly).
        organization: OpenAI organization ID (optional).
        base_url: Custom base URL for API requests (optional, for proxies).
        timeout: Request timeout in seconds (default 300 for large files).
        max_retries: Maximum number of retries on API errors.
        max_upload_size_mb: Maximum upload size accepted by the transcription API.
        chunk_target_size_mb: Target chunk size used before reaching max_upload_size_mb.
        chunk_min_duration_seconds: Minimum chunk duration when retrying chunk sizing.
        chunk_prompt_chars: Number of previous transcript characters used as context
            for the next chunk.

    Example:
        >>> from audiocore.config.openai_config import OpenAIConfig
        >>> config = OpenAIConfig(api_key="sk-...")
        >>> config.api_key.get_secret_value()  # Access actual key
        'sk-...'
        >>> str(config)  # Shows ********** for security
        "api_key=SecretStr('**********') ..."

    Security:
        - API keys use SecretStr to prevent __repr__ exposure
        - API keys are never logged
        - model_dump() hides secrets by default
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key (from OPENAI_API_KEY env var or passed directly)",
    )
    organization: str | None = Field(
        default=None,
        description="OpenAI organization ID (optional)",
    )
    base_url: str | None = Field(
        default=None,
        description="Custom base URL for API requests (optional, for proxies)",
    )
    timeout: float = Field(
        default=300.0,
        ge=1.0,
        le=3600.0,
        description="Request timeout in seconds (default 300 for large files)",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Maximum number of retries on API errors",
    )
    max_upload_size_mb: float = Field(
        default=25.0,
        ge=1.0,
        le=512.0,
        description="Maximum audio upload size for OpenAI transcription requests",
    )
    chunk_target_size_mb: float = Field(
        default=24.0,
        ge=1.0,
        le=512.0,
        description="Target size for automatic large-audio chunks",
    )
    chunk_min_duration_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=3600.0,
        description="Minimum chunk duration when reducing chunk size after oversize output",
    )
    chunk_prompt_chars: int = Field(
        default=1000,
        ge=0,
        le=4000,
        description="Previous transcript characters sent as prompt context for chunk continuity",
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def coerce_api_key(cls, v: Any) -> SecretStr | None:
        """Accept plain str and wrap it in SecretStr for strict mode compatibility."""
        if v is None:
            return None
        if isinstance(v, str):
            return SecretStr(v)
        if isinstance(v, SecretStr):
            return v
        raise ValueError(f"Expected str or SecretStr for api_key, got {type(v).__name__}")

    @field_validator(
        "timeout",
        "max_upload_size_mb",
        "chunk_target_size_mb",
        "chunk_min_duration_seconds",
        mode="before",
    )
    @classmethod
    def coerce_float_fields(cls, v: Any) -> float:
        """Accept string float values from nested environment variables."""
        if isinstance(v, bool):
            raise ValueError("value must be a number")
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, str):
            return float(v.strip())
        return v

    @field_validator("max_retries", mode="before")
    @classmethod
    def coerce_max_retries(cls, v: Any) -> int:
        """Accept string retry counts from nested environment variables."""
        if isinstance(v, bool):
            raise ValueError("max_retries must be an integer")
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            return int(v.strip())
        return v

    @field_validator("chunk_prompt_chars", mode="before")
    @classmethod
    def coerce_chunk_prompt_chars(cls, v: Any) -> int:
        """Accept string prompt-length values from nested environment variables."""
        if isinstance(v, bool):
            raise ValueError("chunk_prompt_chars must be an integer")
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            return int(v.strip())
        return v

    @model_validator(mode="after")
    def validate_chunk_size_order(self) -> Self:
        """Ensure chunks target a smaller size than the API upload limit."""
        if self.chunk_target_size_mb >= self.max_upload_size_mb:
            raise ValueError(
                "chunk_target_size_mb must be less than max_upload_size_mb "
                "so chunking keeps a safety margin"
            )
        return self
