"""Pipeline-specific exceptions for AudioCore.

This module provides exceptions specific to the Pipeline orchestration,
including stage-specific errors and partial result preservation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from audiocore.errors.base import AudioCoreError
from audiocore.pipeline.progress import PipelineStage

if TYPE_CHECKING:
    from audiocore.models import TranscriptionResult


class PipelineError(AudioCoreError):
    """Base exception for pipeline-related errors.

    This exception is raised when pipeline orchestration fails,
    providing context about which pipeline stage failed and why.

    Attributes:
        error_code: Always AUD-501 (pipeline error)
        stage: The pipeline stage that failed (if applicable)
        original_error: The underlying exception that caused the failure

    Example:
        >>> raise PipelineError(
        ...     "Pipeline failed during audio extraction",
        ...     context={"file": "audio.mp3"},
        ...     stage=PipelineStage.EXTRACTING,
        ...     original_error=extraction_error
        ... )
    """

    error_code: str = "AUD-501"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        stage: PipelineStage | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize PipelineError.

        Args:
            message: Human-readable error description.
            context: Dictionary of contextual information.
            suggestions: List of actionable suggestions for resolution.
            stage: The pipeline stage that failed (if applicable).
            original_error: The underlying exception that caused the failure.
        """
        self.stage = stage
        self.original_error = original_error

        # Add stage to context if provided
        if stage is not None:
            context = context or {}
            context["stage"] = stage.value

        if suggestions is None:
            suggestions = [
                "Check input file format and integrity",
                "Verify all required dependencies are installed",
                "Try with different transcription options",
                "Check system resources (memory, disk space)",
            ]

        super().__init__(message, context, suggestions, original_error)


class PipelineStageError(PipelineError):
    """Exception raised when a specific pipeline stage fails.

    This exception wraps underlying exceptions from individual pipeline
    stages (probe, extraction, VAD, backend) with additional context
    about which stage failed and what was attempted.

    Attributes:
        error_code: AUD-502 (pipeline stage failure)
        stage: The pipeline stage that failed
        original_error: The underlying exception from the stage

    Example:
        >>> try:
        ...     audio_path = extract_audio(input_path, output_path)
        ... except MediaError as e:
        ...     raise PipelineStageError(
        ...         "Failed to extract audio",
        ...         stage=PipelineStage.EXTRACTING,
        ...         original_error=e
        ...     )
    """

    error_code: str = "AUD-502"

    def __init__(
        self,
        message: str,
        stage: PipelineStage,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize PipelineStageError.

        Args:
            message: Human-readable error description.
            stage: The pipeline stage that failed (required).
            context: Dictionary of contextual information.
            suggestions: List of actionable suggestions.
            original_error: The underlying exception from the stage.
        """
        # Add stage to context
        context = context or {}
        context["stage"] = stage.value

        # Add original error type to context if available
        if original_error is not None:
            context["original_error_type"] = type(original_error).__name__

        # Stage-specific suggestions
        if suggestions is None:
            stage_suggestions = {
                PipelineStage.PROBING: [
                    "Check if ffprobe is installed and in PATH",
                    "Verify the media file exists and is readable",
                    "Try a different media format",
                ],
                PipelineStage.EXTRACTING: [
                    "Check if ffmpeg is installed and in PATH",
                    "Verify sufficient disk space for temp files",
                    "Check media file for corruption",
                ],
                PipelineStage.VAD: [
                    "Verify VAD model is available",
                    "Check system memory",
                    "Try whole-file transcription (skip VAD)",
                ],
                PipelineStage.SELECTING: [
                    "Install at least one transcription backend",
                    "Check API keys are configured",
                    "Verify network connectivity",
                ],
                PipelineStage.TRANSCRIBING: [
                    "Check backend availability",
                    "Verify API keys or model files",
                    "Try with a smaller model",
                ],
                PipelineStage.FORMATTING: [
                    "Check transcription result integrity",
                    "Verify output format is valid",
                ],
            }
            suggestions = stage_suggestions.get(
                stage,
                [
                    "Check pipeline stage specific requirements",
                ],
            )

        super().__init__(message, context, suggestions, stage, original_error)


class PipelineCancelledError(PipelineError):
    """Exception raised when pipeline execution is cancelled.

    This exception is raised when a CancellationToken signals cancellation
    during pipeline execution. Unlike CancelledError (which is a simpler
    exception), this preserves pipeline context about where cancellation occurred.

    Attributes:
        error_code: AUD-503 (pipeline cancelled)
        stage: The pipeline stage where cancellation was detected

    Example:
        >>> token = CancellationToken()
        >>> token.cancel()
        >>> # During pipeline execution:
        >>> raise PipelineCancelledError(
        ...     "User cancelled transcription",
        ...     stage=PipelineStage.TRANSCRIBING
        ... )
    """

    error_code: str = "AUD-503"

    def __init__(
        self,
        message: str = "Pipeline execution was cancelled",
        stage: PipelineStage | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize PipelineCancelledError.

        Args:
            message: Human-readable cancellation message.
            stage: The pipeline stage where cancellation occurred.
            context: Dictionary of contextual information.
            suggestions: List of suggestions for handling cancellation.
        """
        if suggestions is None:
            suggestions = [
                "Cancelling is intentional - review partial results if available",
                "Create a new CancellationToken to retry",
                "Check if cancellation was expected",
            ]

        if context is None:
            context = {}

        if stage is not None:
            context["stage"] = stage.value

        super().__init__(message, context, suggestions, stage)


class PartialResultError(PipelineError):
    """Exception raised when pipeline fails but partial results are available.

    This exception preserves partial transcription results when the
    pipeline fails partway through, allowing users to recover some
    progress instead of losing everything.

    Attributes:
        error_code: AUD-504 (partial result)
        partial_result: The partial TranscriptionResult (if available)
        failed_segments: List of segments that failed to transcribe

    Example:
        >>> # Pipeline transcribes 10 segments, last one fails:
        >>> successful = segments[:9]
        >>> failed = segments[9]
        >>> raise PartialResultError(
        ...     "Transcription failed on segment 10",
        ...     partial_result=partial_result,
        ...     original_error=backend_error
        ... )
    """

    error_code: str = "AUD-504"

    def __init__(
        self,
        message: str,
        partial_result: TranscriptionResult | None = None,
        failed_segments: list[Any] | None = None,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        original_error: Exception | None = None,
        stage: PipelineStage | None = None,
    ) -> None:
        """Initialize PartialResultError.

        Args:
            message: Human-readable error description.
            partial_result: Partial transcription result (if available).
            failed_segments: List of segments that failed transcription.
            context: Dictionary of contextual information.
            suggestions: List of actionable suggestions.
            original_error: The underlying exception that caused failure.
            stage: The pipeline stage where failure occurred.
        """
        self.partial_result = partial_result
        self.failed_segments = failed_segments or []

        # Add partial result info to context
        context = context or {}
        if partial_result is not None:
            context["segments_completed"] = len(partial_result.segments)
        if failed_segments:
            context["segments_failed"] = len(failed_segments)

        if suggestions is None:
            suggestions = [
                "Partial results are preserved - check .partial_result",
                "Review failed segments in .failed_segments",
                "Retry with failed segments only if needed",
                "Consider adjusting VAD or backend settings",
            ]

        super().__init__(message, context, suggestions, stage, original_error)


__all__ = [
    "PipelineError",
    "PipelineStageError",
    "PipelineCancelledError",
    "PartialResultError",
]
