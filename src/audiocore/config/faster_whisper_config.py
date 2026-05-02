"""Faster-Whisper configuration for AudioCore.

This module provides FasterWhisperConfig for configuring faster-whisper
backend parameters including model size, device selection, decoding
parameters, and VAD settings.

Key Features:
- Model size configuration (tiny, base, small, medium, large)
- Automatic device selection (CUDA, MPS, CPU)
- Decoding parameters (beam size, temperature, etc.)
- Built-in VAD toggle

Example:
    >>> from audiocore.config.faster_whisper_config import FasterWhisperConfig
    >>> from audiocore.types import ModelSize
    >>> config = FasterWhisperConfig(model_size=ModelSize.BASE, device="cuda")
    >>> config.model_size
    <ModelSize.BASE: 'base'>
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from audiocore.types.backend import ModelSize


class ComputeType(StrEnum):
    """Valid compute types for faster-whisper inference.

    Compute type affects:
    - Inference speed
    - Memory usage
    - Accuracy

    Options:
        DEFAULT: Default float32 precision
        INT8: 8-bit quantization (faster, less memory)
        FLOAT16: 16-bit floating point (faster on GPU)
        INT8_FLOAT16: Mixed precision 8-bit + float16
    """

    DEFAULT = "default"
    INT8 = "int8"
    FLOAT16 = "float16"
    INT8_FLOAT16 = "int8_float16"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a string to ComputeType case-insensitively.

        Args:
            value: String to parse

        Returns:
            ComputeType enum member

        Raises:
            ValueError: If value is not valid
        """
        normalized = value.lower().replace("-", "_").replace(" ", "_")
        try:
            return cls(normalized)
        except ValueError:
            valid_options = ", ".join(f"'{m.value}'" for m in cls)
            raise ValueError(
                f"Invalid compute type '{value}'. Valid options: {valid_options}"
            ) from None


class FasterWhisperConfig(BaseModel):
    """Configuration for faster-whisper backend.

    Stores model configuration, device settings, and decoding parameters
    for the faster-whisper transcription backend.

    Attributes:
        model_size: Model size (tiny, base, small, medium, large).
        device: Device for inference (None=auto-detect, "cuda", "mps", "cpu").
        compute_type: Compute type (default, int8, float16, int8_float16).
        language: Language code (None=auto-detect, or "en", "es", etc.).
        beam_size: Beam search size (1-20).
        best_of: Number of candidates to consider (>= beam_size).
        patience: Beam search patience factor.
        temperature: Fallback temperature for sampling (0.0-1.0).
        compression_ratio_threshold: Log compression ratio threshold.
        log_prob_threshold: Log probability threshold.
        no_speech_threshold: No speech probability threshold.
        condition_on_previous_text: Use previous text as context.
        initial_prompt: Initial prompt for context.
        word_timestamps: Generate word-level timestamps.
        vad_filter: Use faster-whisper built-in VAD.

    Example:
        >>> config = FasterWhisperConfig(
        ...     model_size=ModelSize.BASE,
        ...     device="cuda",
        ...     beam_size=5,
        ...     vad_filter=True
        ... )
        >>> config.beam_size
        5

    Validation:
        - device must be None, "cuda", "mps", or "cpu"
        - compute_type must be valid ComputeType
        - beam_size must be > 0 and <= 20
        - best_of must be >= beam_size
        - temperature must be in [0.0, 1.0]
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    # Model configuration
    model_size: ModelSize = Field(
        default=ModelSize.BASE,
        description="Model size (tiny, base, small, medium, large)",
    )
    device: str | None = Field(
        default=None,
        description="Device for inference (None=auto-detect, cuda, mps, cpu)",
    )
    compute_type: ComputeType = Field(
        default=ComputeType.DEFAULT,
        description="Compute type (default, int8, float16, int8_float16)",
    )
    language: str | None = Field(
        default=None,
        description="Language code (None=auto-detect, or en, es, etc.)",
    )

    # Decoding parameters
    beam_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Beam search size (1-20)",
    )
    best_of: int = Field(
        default=5,
        ge=1,
        description="Number of candidates to consider (>= beam_size)",
    )
    patience: float = Field(
        default=1.0,
        ge=1.0,
        le=5.0,
        description="Beam search patience factor",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fallback temperature for sampling (0.0-1.0)",
    )

    # Thresholds
    compression_ratio_threshold: float = Field(
        default=2.4,
        ge=1.0,
        le=10.0,
        description="Log compression ratio threshold",
    )
    log_prob_threshold: float = Field(
        default=-1.0,
        ge=-5.0,
        le=0.0,
        description="Log probability threshold",
    )
    no_speech_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="No speech probability threshold",
    )

    # Advanced options
    condition_on_previous_text: bool = Field(
        default=True,
        description="Use previous text as context",
    )
    initial_prompt: str | None = Field(
        default=None,
        description="Initial prompt for context",
    )
    word_timestamps: bool = Field(
        default=True,
        description="Generate word-level timestamps",
    )
    vad_filter: bool = Field(
        default=True,
        description="Use faster-whisper built-in VAD",
    )

    @field_validator("device", mode="before")
    @classmethod
    def validate_device(cls, v: str | None) -> str | None:
        """Validate device string.

        Args:
            v: Device value to validate

        Returns:
            Validated device string or None

        Raises:
            ValueError: If device is not valid
        """
        if v is None:
            return v
        valid_devices = {"cuda", "mps", "cpu", "auto"}
        if isinstance(v, str):
            normalized = v.lower()
            if normalized not in valid_devices:
                raise ValueError(
                    f"Invalid device '{v}'. Valid options: None, 'cuda', 'mps', 'cpu', 'auto'"
                )
            return normalized
        raise ValueError(f"Invalid device type: {type(v)}")

    @field_validator("language", mode="before")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
        """Validate language code.

        Args:
            v: Language code to validate

        Returns:
            Validated language code or None

        Raises:
            ValueError: If language code is invalid
        """
        if v is None:
            return v
        # Accept 2-3 char codes or BCP 47 tags (e.g., "en-US", "zh-CN")
        if isinstance(v, str):
            normalized = v.lower()
            if not re.match(r"^[a-z]{2,3}(-[a-z]{2,3})?$", normalized):
                raise ValueError(
                    f"Invalid language code '{v}'. Expected 2-3 character code (e.g., 'en', 'es') or BCP 47 tag (e.g., 'en-US')"
                )
            return normalized
        return v

    @field_validator("compute_type", mode="before")
    @classmethod
    def validate_compute_type(cls, v: Any) -> ComputeType:
        """Validate and coerce compute_type.

        Args:
            v: Compute type value to validate

        Returns:
            ComputeType enum member

        Raises:
            ValueError: If compute type is invalid
        """
        if isinstance(v, ComputeType):
            return v
        if isinstance(v, str):
            return ComputeType.parse(v)
        raise ValueError(f"Invalid compute type: {v}")

    @field_validator("model_size", mode="before")
    @classmethod
    def validate_model_size(cls, v: Any) -> ModelSize:
        """Validate and coerce model_size.

        Args:
            v: Model size value to validate

        Returns:
            ModelSize enum member

        Raises:
            ValueError: If model size is invalid
        """
        if isinstance(v, ModelSize):
            return v
        if isinstance(v, str):
            return ModelSize.parse(v)
        raise ValueError(f"Invalid model size: {v}")

    @model_validator(mode="after")
    def validate_beam_search(self) -> Self:
        """Validate beam_size and best_of relationship.

        Returns:
            Validated config

        Raises:
            ValueError: If best_of < beam_size
        """
        if self.best_of < self.beam_size:
            raise ValueError(f"best_of ({self.best_of}) must be >= beam_size ({self.beam_size})")
        return self

    @classmethod
    def get_available_models(cls) -> list[str]:
        """Return list of available faster-whisper models.

        Returns:
            List of model names (tiny, base, small, medium, large)
        """
        return [size.value for size in ModelSize]

    @property
    def model_name(self) -> str:
        """Get the model name for faster-whisper.

        Returns:
            Model name string
        """
        return self.model_size.value
