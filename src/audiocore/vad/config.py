"""Configuration for Voice Activity Detection.

This module provides VADConfig for configuring Silero VAD parameters
for speech detection and segmentation.
"""

from pydantic import BaseModel, Field, model_validator


class VADConfig(BaseModel):
    """Configuration for Voice Activity Detection.

    Controls how Silero VAD detects and segments speech in audio.

    Attributes:
        min_segment_duration: Minimum segment duration in seconds.
            Shorter segments are merged with neighbors if within gap threshold.
        max_segment_duration: Maximum segment duration in seconds.
            Longer segments are split at silence points.
        speech_threshold: Probability threshold for speech detection (0.0-1.0).
            Higher values = more strict speech detection.
        silence_threshold: Probability threshold for silence detection (0.0-1.0).
            Lower values = more permissive silence detection.
        speech_pad_ms: Padding in milliseconds added to start/end of speech segments.
        min_silence_duration_ms: Minimum silence duration in milliseconds to split segments.
        window_size_samples: Window size in samples for VAD processing.
            Silero optimal values: 512, 768, or 1024.
    """

    model_config = {"strict": True, "extra": "forbid"}

    min_segment_duration: float = Field(
        default=0.5,
        ge=0.1,
        le=10.0,
        description="Minimum segment duration in seconds",
    )
    max_segment_duration: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Maximum segment duration in seconds",
    )
    speech_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Speech probability threshold for detection",
    )
    silence_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Silence probability threshold",
    )
    speech_pad_ms: int = Field(
        default=30,
        ge=0,
        le=500,
        description="Padding in milliseconds around speech segments",
    )
    min_silence_duration_ms: int = Field(
        default=100,
        ge=50,
        le=1000,
        description="Minimum silence duration to split segments",
    )
    window_size_samples: int = Field(
        default=512,
        ge=256,
        le=1024,
        description="Window size in samples for VAD processing",
    )

    @model_validator(mode="after")
    def validate_thresholds(self) -> "VADConfig":
        """Validate threshold relationships.

        Ensures speech_threshold > silence_threshold for proper detection.
        Ensures min_segment_duration < max_segment_duration.

        Returns:
            VADConfig: Validated config instance.

        Raises:
            ValueError: If thresholds or durations are invalid.
        """
        if self.speech_threshold <= self.silence_threshold:
            raise ValueError(
                f"speech_threshold ({self.speech_threshold}) must be greater than "
                f"silence_threshold ({self.silence_threshold})"
            )
        if self.min_segment_duration >= self.max_segment_duration:
            raise ValueError(
                f"min_segment_duration ({self.min_segment_duration}) must be less than "
                f"max_segment_duration ({self.max_segment_duration})"
            )
        return self
