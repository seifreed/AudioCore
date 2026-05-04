"""Configuration settings for AudioCore.

Provides AppConfig model using pydantic-settings BaseSettings for
environment variable configuration with AUDIOCORE_ prefix and secure
API key handling via SecretStr.
"""

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from audiocore.config.faster_whisper_config import FasterWhisperConfig
from audiocore.config.openai_config import OpenAIConfig
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy
from audiocore.vad.config import VADConfig


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
        language: Language code for transcription (e.g., "en", "es") or None
        output_format: Output format for transcription results
        backend_preference: Policy for automatic backend selection
        vad: Voice Activity Detection configuration
    """

    model_config = SettingsConfigDict(
        env_prefix="AUDIOCORE_",
        case_sensitive=False,
        env_file=None,
        extra="forbid",
        env_nested_delimiter="__",
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key for cloud transcription. Stored securely.",
    )
    backend: BackendType = Field(
        default=BackendType.AUTO,
        description="Backend type for transcription: openai, faster_whisper, or auto",
    )
    # NOTE: Field named 'model' to match AUDIOCORE_MODEL env var
    # model_size property provides backwards-compatible access
    model: ModelSize = Field(
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
    ffprobe_path: str = Field(
        default="ffprobe",
        description="Path to ffprobe binary for media analysis",
    )
    ffmpeg_path: str = Field(
        default="ffmpeg",
        description="Path to ffmpeg binary for media processing",
    )
    vad: VADConfig = Field(
        default_factory=VADConfig,
        description="Voice Activity Detection configuration",
    )
    openai: OpenAIConfig = Field(
        default_factory=lambda: OpenAIConfig(),
        description="OpenAI Whisper API configuration",
    )
    faster_whisper: FasterWhisperConfig = Field(
        default_factory=FasterWhisperConfig,
        description="Faster-Whisper local backend configuration",
    )

    @field_validator("backend", mode="before")
    @classmethod
    def validate_backend(cls, v: Any) -> BackendType:
        """Validate and coerce backend type from string.

        Args:
            v: Value to validate (string or BackendType)

        Returns:
            BackendType enum member

        Raises:
            ValueError: If value is not a valid backend type
        """
        if isinstance(v, BackendType):
            return v
        return BackendType.parse(v)

    @field_validator("model", mode="before")
    @classmethod
    def validate_model(cls, v: Any) -> ModelSize:
        """Validate and coerce model size from string.

        Args:
            v: Value to validate (string or ModelSize)

        Returns:
            ModelSize enum member

        Raises:
            ValueError: If value is not a valid model size
        """
        if isinstance(v, ModelSize):
            return v
        return ModelSize.parse(v)

    @field_validator("output_format", mode="before")
    @classmethod
    def validate_output_format(cls, v: Any) -> OutputFormat:
        """Validate and coerce output format from string.

        Args:
            v: Value to validate (string or OutputFormat)

        Returns:
            OutputFormat enum member

        Raises:
            ValueError: If value is not a valid output format
        """
        if isinstance(v, OutputFormat):
            return v
        return OutputFormat.parse(v)

    @field_validator("backend_preference", mode="before")
    @classmethod
    def validate_backend_preference(cls, v: Any) -> SelectionPolicy:
        """Validate and coerce selection policy from string.

        Args:
            v: Value to validate (string or SelectionPolicy)

        Returns:
            SelectionPolicy enum member

        Raises:
            ValueError: If value is not a valid selection policy
        """
        if isinstance(v, SelectionPolicy):
            return v
        return SelectionPolicy.parse(v)

    @field_validator("ffmpeg_path", "ffprobe_path", mode="before")
    @classmethod
    def validate_media_tool_path(cls, v: Any) -> str:
        """Validate ffmpeg/ffprobe executable path fields."""
        if isinstance(v, Path):
            v = str(v)
        if not isinstance(v, str):
            raise ValueError(f"Expected string path, got {type(v).__name__}")

        value = v.strip()
        if not value:
            raise ValueError("Executable path must not be empty")
        if "\x00" in value:
            raise ValueError("Executable path must not contain NUL bytes")
        return value

    @property
    def model_size(self) -> ModelSize:
        """Alias for model field for backwards compatibility.

        Returns:
            ModelSize enum value for the configured model size.
        """
        return self.model

    @model_validator(mode="after")
    def reconcile_api_keys(self) -> "AppConfig":
        """Propagate top-level openai_api_key to openai.api_key if not set.

        Resolves the ambiguity between AUDIOCORE_OPENAI_API_KEY (top-level)
        and AUDIOCORE_OPENAI__API_KEY (nested). Top-level takes priority.

        Returns:
            Self, after reconciliation.
        """
        if self.openai_api_key is not None:
            key_value = self.openai_api_key.get_secret_value()
            if key_value:
                # Rebuild the openai sub-config to keep Pydantic validation intact
                openai_data = self.openai.model_dump()
                openai_data["api_key"] = self.openai_api_key
                self.openai = type(self.openai).model_validate(openai_data)
        return self
