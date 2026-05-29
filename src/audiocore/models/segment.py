"""Segment model for transcription time segments with validation."""

from __future__ import annotations

import math
from typing import Self

from pydantic import BaseModel, Field, model_validator


class Word(BaseModel):
    """A single word with its timing and optional confidence.

    Word-level timestamps are produced when a backend is asked for them
    (``TranscriptionOptions.word_timestamps``). Both faster-whisper (native
    word timestamps) and the OpenAI Whisper API (``timestamp_granularities``)
    can emit them; the backend layer normalizes both into this model.

    Attributes:
        word: The word text, including any leading/trailing whitespace the
            backend attaches (kept verbatim so the original spacing survives).
        start_time: Start time in seconds (>= 0, finite).
        end_time: End time in seconds (>= 0, finite, and >= start_time).
        confidence: Optional probability between 0 and 1 (faster-whisper only;
            the OpenAI API does not return per-word confidence).

    Example:
        >>> word = Word(word="Hello", start_time=0.0, end_time=0.5)
        >>> word.word
        'Hello'
    """

    model_config = {"strict": True, "extra": "forbid"}

    word: str = Field(description="The word text")
    start_time: float = Field(ge=0, description="Start time of the word in seconds")
    end_time: float = Field(ge=0, description="End time of the word in seconds")
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Confidence score between 0 and 1 (optional)",
    )

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        """Validate that word times are finite and end_time >= start_time.

        Raises:
            ValueError: If time values are inf/NaN or end_time < start_time.
        """
        for field_name, value in [("start_time", self.start_time), ("end_time", self.end_time)]:
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite, got {value}")
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be >= start_time ({self.start_time})"
            )
        return self


class Segment(BaseModel):
    """A time-segmented portion of a transcription.

    Represents a single segment of transcribed audio with timing,
    text content, and optional confidence score.

    Attributes:
        start_time: Start time in seconds (must be >= 0, finite).
        end_time: End time in seconds (must be >= 0, finite, and >= start_time).
        text: The transcribed text content (may be empty before transcription).
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
        description="Transcribed text content for this segment",
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Confidence score between 0 and 1 (optional)",
    )
    words: list[Word] | None = Field(
        default=None,
        description="Optional word-level timestamps (present when word_timestamps is enabled)",
    )

    @model_validator(mode="after")
    def validate_time_order(self) -> Self:
        """Validate that time values are finite and end_time >= start_time.

        Raises:
            ValueError: If time values are inf/NaN or end_time < start_time.
        """
        for field_name, value in [("start_time", self.start_time), ("end_time", self.end_time)]:
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite, got {value}")
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be >= start_time ({self.start_time})"
            )
        return self
