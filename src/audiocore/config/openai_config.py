"""OpenAI-specific configuration for AudioCore.

This module provides OpenAIConfig for configuring OpenAI Whisper API
parameters including API key security, organization, base URL, and
request settings.

Key Features:
- SecretStr for API key protection
- Configurable timeout and retry settings
- Optional organization and base URL for proxies
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr


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

    api_key: Annotated[SecretStr | None, Field(default=None)] = Field(
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
    timeout: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Request timeout in seconds (default 300 for large files)",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Maximum number of retries on API errors",
    )
