"""Segment model for transcription time segments with validation."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Segment(BaseModel):
    """A time-segmented portion of a transcription.

    Represents a single segment of transcribed audio with timing,
    text content, and optional confidence score.

    Attributes:
        start_time: Start time in seconds (must be >= 0).
        end_time: End time in seconds (must be >= 0 and >= start_time).
        text: The transcribed text content (must not be empty).
        confidence: Optional confidence score between 0 and 1.

    Example:
        >>> segment = Segment(start_time=0.0, end_time=5.0, text="Hello world")
        >>> segment.text
        'Hello world'
        >>> segment.model_dump()
        {'start_time': 0.0, 'end_time': 5.0, 'text': 'Hello world', 'confidence': None}
    """

    model_config = {"strict": True, "extra": "forbid"}

    start_time: float = Field(ge=0, description="Start time of the segment in seconds")
    end_time: float = Field(ge=0, description="End time of the segment in seconds")
    text: str = Field(
        default="",
        description="Transcribed text content for this segment (empty before transcription)",
    )
    confidence: Optional[float] = Field(
        default=None, ge=0, le=1, description="Confidence score between 0 and 1 (optional)"
    )

    @model_validator(mode="after")
    def validate_time_order(self) -> "Segment":
        """Validate that end_time >= start_time.

        Raises:
            ValueError: If end_time is less than start_time.
        """
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be >= start_time ({self.start_time})"
            )
        return self
