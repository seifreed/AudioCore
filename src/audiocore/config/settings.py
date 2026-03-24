"""Configuration settings for AudioCore.

Provides AppConfig model using pydantic-settings BaseSettings for
environment variable configuration with AUDIOCORE_ prefix and secure
API key handling via SecretStr.
"""

from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables.

    All environment variables use AUDIOCORE_ prefix for clear namespacing.
    API key is stored securely using SecretStr to prevent accidental exposure.

    Example:
        >>> import os
        >>> os.environ['AUDIOCORE_BACKEND'] = 'openai'
        >>> config = AppConfig()
        >>> config.backend
        <BackendType.OPENAI: 'openai'>

    Attributes:
        openai_api_key: OpenAI API key for cloud transcription (secured)
        backend: Backend type for transcription (OPENAI, FASTER_WHISPER, AUTO)
        model_size: Model size for transcription (TINY, BASE, SMALL, MEDIUM, LARGE)
        language: Language code for transcription (e.g., "en", "es") or None
        output_format: Output format for transcription results
        backend_preference: Policy for automatic backend selection
    """

    model_config = SettingsConfigDict(
        env_prefix="AUDIOCORE_",
        case_sensitive=False,
        env_file=None,
        extra="forbid",
    )

    openai_api_key: Annotated[SecretStr, Field(default_factory=lambda: SecretStr(""))] = Field(
        description="OpenAI API key for cloud transcription. Stored securely.",
    )
    backend: BackendType = Field(
        default=BackendType.AUTO,
        description="Backend type for transcription: openai, faster_whisper, or auto",
    )
    model_size: ModelSize = Field(
        default=ModelSize.BASE,
        description="Model size for transcription: tiny, base, small, medium, or large",
    )
    language: str | None = Field(
        default=None,
        description="Language code for transcription (e.g., 'en', 'es')",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT,
        description="Output format for transcription: text, json, srt, or vtt",
    )
    backend_preference: SelectionPolicy = Field(
        default=SelectionPolicy.AUTO,
        description="Policy for automatic backend selection: prefer_local, prefer_cloud, or auto",
    )
