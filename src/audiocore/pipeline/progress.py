"""Progress callback types for pipeline stage notifications.

This module defines the types and protocols for progress tracking
during pipeline execution, enabling users to receive stage notifications
and progress updates.

Example:
    >>> def my_callback(stage: PipelineStage, progress: float, message: str):
    ...     print(f"[{stage.value}] {progress:.0%} - {message}")
    ...
    >>> pipeline = Pipeline()
    >>> result = pipeline.transcribe("audio.mp3", progress_callback=my_callback)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class PipelineStage(str, Enum):
    """Stages of the transcription pipeline.

    Each stage represents a distinct phase in the transcription process,
    allowing progress callbacks to track where the pipeline is in its
    execution.

    Attributes:
        PROBING: Media probing for metadata extraction
        EXTRACTING: Audio extraction to WAV format
        VAD: Voice Activity Detection processing
        SELECTING: Backend selection and availability checking
        TRANSCRIBING: Audio transcription execution
        FORMATTING: Output formatting (text/JSON)
        COMPLETE: Pipeline completion
    """

    PROBING = "probing"
    EXTRACTING = "extracting"
    VAD = "vad"
    SELECTING = "selecting"
    TRANSCRIBING = "transcribing"
    FORMATTING = "formatting"
    COMPLETE = "complete"


class ProgressCallback(Protocol):
    """Protocol for progress callback functions.

    Any callable matching this signature can be used as a progress
    callback. The progress percentage (0.0 to 1.0) and stage-specific
    messages are provided.

    Example:
        >>> def progress_handler(
        ...     stage: PipelineStage,
        ...     progress: float,
        ...     message: str,
        ... ) -> None:
        ...     logger.info(f"[{stage.value}] {progress:.0%}: {message}")

        >>> result = pipeline.transcribe(
        ...     "audio.mp3",
        ...     progress_callback=progress_handler,
        ... )
    """

    def __call__(
        self,
        stage: PipelineStage,
        progress: float,
        message: str,
    ) -> None:
        """Called during pipeline execution to report progress.

        Args:
            stage: The current pipeline stage.
            progress: Progress within the stage (0.0 to 1.0).
                For stage transitions, this is typically 0.0 at start
                and 1.0 at completion.
            message: Human-readable description of current operation.
        """
        ...


@dataclass
class ProgressEvent:
    """Dataclass for progress event emission.

    Represents a single progress event with all associated data.
    Useful for event-based systems or logging frameworks.

    Attributes:
        stage: The pipeline stage this event belongs to.
        progress: Progress percentage (0.0 to 1.0).
        message: Human-readable description of current operation.
        timestamp: Optional timestamp of the event (for event ordering).

    Example:
        >>> event = ProgressEvent(
        ...     stage=PipelineStage.TRANSCRIBING,
        ...     progress=0.5,
        ...     message="Transcribing segment 3 of 6",
        ... )
        >>> print(f"{event.stage.value}: {event.progress:.0%}")
    """

    stage: PipelineStage
    progress: float
    message: str
    timestamp: float | None = None
