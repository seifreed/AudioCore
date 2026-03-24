"""Configuration settings for AudioCore.

Provides AppConfig model using pydantic-settings BaseSettings for
environment variable configuration with AUDIOCORE_ prefix and secure
API key handling via SecretStr.
"""

from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator
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

    @property
    def model_size(self) -> ModelSize:
        """Alias for model field for backwards compatibility.

        Returns:
            ModelSize enum value for the configured model size.
        """
        return self.model
