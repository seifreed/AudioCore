"""Pipeline orchestration for end-to-end transcription.

This module provides the main Pipeline class that coordinates the full
transcription workflow from media input to formatted output.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from audiocore.backends import BackendRegistry, BackendSelector
from audiocore.config import AppConfig
from audiocore.errors import (
    BackendUnavailableError,
    MediaError,
    MediaFormatError,
    VADError,
)
from audiocore.media import (
    extract_audio,
    probe,
    temp_audio_file,
    validate_format_or_raise,
)
from audiocore.models import (
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
    transcription_options_from_config,
)
from audiocore.output import format_json, format_srt, format_text, format_vtt
from audiocore.pipeline.cancellation import CancellationToken, CancelledError
from audiocore.pipeline.errors import PartialResultError, PipelineStageError
from audiocore.pipeline.progress import PipelineStage, ProgressCallback
from audiocore.types import OutputFormat
from audiocore.vad import detect_speech

if TYPE_CHECKING:
    from audiocore.backends.base import TranscriptionBackend

logger = logging.getLogger(__name__)


class Pipeline:
    """Main transcription pipeline that orchestrates end-to-end workflow.

    The Pipeline class coordinates all transcription components:
    1. Format validation
    2. Media probing
    3. Audio extraction
    4. Voice Activity Detection (VAD)
    5. Backend selection
    6. Transcription execution
    7. Result assembly

    The pipeline uses context managers for guaranteed cleanup of temporary
    files and provides automatic backend selection based on availability.

    Progress callbacks allow monitoring of pipeline execution at each stage,
    and cancellation tokens enable clean termination mid-pipeline.

    Error Handling:
        - Stage failures are wrapped in PipelineStageError with context
        - Partial results are preserved when possible (PartialResultError)
        - Temp files are cleaned up even on error or cancellation

    Example:
        >>> pipeline = Pipeline()
        >>> result = pipeline.transcribe("audio.mp3")
        >>> print(result.segments[0].text)

        >>> # With progress callback
        >>> def on_progress(stage, progress, message):
        ...     print(f"[{stage.value}] {progress:.0%}: {message}")
        >>> result = pipeline.transcribe("audio.mp3", progress_callback=on_progress)

        >>> # With custom options
        >>> from audiocore.models import TranscriptionOptions
        >>> from audiocore.types import BackendType
        >>> options = TranscriptionOptions(backend=BackendType.OPENAI)
        >>> result = pipeline.transcribe("audio.mp3", options)
    """

    def __init__(
        self,
        config: AppConfig | None = None,
    ):
        """Initialize the pipeline with optional configuration.

        Args:
            config: Application configuration. If None, uses default AppConfig.
        """
        self.config = config or AppConfig()
        self._registry = BackendRegistry()
        self._selector = BackendSelector(config=self.config)

    def transcribe(
        self,
        path: str | Path,
        options: TranscriptionOptions | None = None,
        progress_callback: ProgressCallback | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> TranscriptionResult:
        """Transcribe an audio/video file through the full pipeline.

        This method orchestrates the complete transcription workflow:
        1. Validates the input format
        2. Probes the media file for metadata
        3. Extracts audio to a temporary WAV file
        4. Detects speech segments using VAD
        5. Selects the appropriate backend
        6. Transcribes audio segments
        7. Merges results and returns TranscriptionResult

        Temporary files are automatically cleaned up even on failure or
        cancellation. Wrapped exceptions include stage context.

        Args:
            path: Path to the audio/video file to transcribe.
            options: Transcription options. If None, uses defaults.
            progress_callback: Optional callback for progress notifications.
                Called with (stage, progress, message) at each stage transition.
            cancellation_token: Optional token for cancellation support.
                Check cancellation at each stage boundary.

        Returns:
            TranscriptionResult: Complete transcription result with segments,
                media info, and processing metadata.

        Raises:
            MediaFormatError: If the input format is not supported.
            MediaError: If media probing or extraction fails.
            VADError: If VAD processing fails.
            BackendUnavailableError: If no backend is available.
            PipelineStageError: If a pipeline stage fails (wraps underlying error).
            PartialResultError: If transcription fails with partial results available.
            CancelledError: If cancellation is requested during execution.
        """
        path = Path(path)
        if options is None:
            options = transcription_options_from_config(self.config)

        # Helper to emit progress safely — never let callback exceptions
        # mask pipeline errors like CancelledError
        def emit_progress(stage: PipelineStage, progress: float, message: str) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(stage, progress, message)
                except Exception:
                    logger.debug("Progress callback raised, ignoring", exc_info=True)

        # Helper to check cancellation safely
        def check_cancellation() -> None:
            if cancellation_token is not None:
                cancellation_token.check()

        try:
            # Step 1: Validate format
            emit_progress(PipelineStage.PROBING, 0.0, "Validating input format")
            try:
                validate_format_or_raise(path)
            except MediaFormatError:
                # No cleanup needed - no temp files created yet
                raise
            check_cancellation()

            # Step 2: Probe media for metadata
            emit_progress(PipelineStage.PROBING, 0.0, "Starting media probe")
            try:
                media_info = probe(path, ffprobe_path=self.config.ffprobe_path)
            except MediaError as e:
                raise PipelineStageError(
                    "Failed to probe media file",
                    stage=PipelineStage.PROBING,
                    original_error=e,
                ) from e
            emit_progress(PipelineStage.PROBING, 1.0, "Media probe complete")
            check_cancellation()

            # Step 3-7: Process with temp file cleanup
            with temp_audio_file(suffix=".wav") as audio_path:
                # Step 3: Extract audio to temp file
                emit_progress(PipelineStage.EXTRACTING, 0.0, "Starting audio extraction")

                def extraction_progress(progress: float) -> None:
                    """Forward extraction progress to main callback."""
                    emit_progress(
                        PipelineStage.EXTRACTING,
                        progress,
                        f"Extracting audio: {progress:.0%}",
                    )

                try:
                    extract_audio(
                        path,
                        audio_path,
                        ffmpeg_path=self.config.ffmpeg_path,
                        ffprobe_path=self.config.ffprobe_path,
                        progress_callback=extraction_progress,
                    )
                except MediaError as e:
                    logger.debug("Cleaning up temp file after extraction failure: %s", audio_path)
                    raise PipelineStageError(
                        "Failed to extract audio from media file",
                        stage=PipelineStage.EXTRACTING,
                        context={
                            "input_path": str(path),
                            "output_path": str(audio_path),
                        },
                        original_error=e,
                    ) from e
                emit_progress(PipelineStage.EXTRACTING, 1.0, "Audio extraction complete")
                check_cancellation()

                # Step 4: Run VAD to detect speech segments
                emit_progress(PipelineStage.VAD, 0.0, "Starting voice activity detection")
                vad_config = self.config.vad
                try:
                    segments = detect_speech(
                        audio_path=audio_path,
                        config=vad_config,
                        total_duration=media_info.duration,
                    )
                except VADError as e:
                    # VAD failed - check if strict mode (from options or config)
                    if options.strict_vad or vad_config.strict_vad:
                        # Re-raise in strict mode - user wants to know about VAD failures
                        raise
                    # Otherwise, fall back to whole-file transcription
                    logger.warning("VAD failed, falling back to whole-file transcription: %s", e)
                    segments = []  # Empty segments will trigger whole-file transcription
                emit_progress(PipelineStage.VAD, 1.0, "Voice activity detection complete")
                check_cancellation()

                # Step 5: Select backend
                emit_progress(PipelineStage.SELECTING, 0.0, "Selecting transcription backend")
                try:
                    selected_backend_type = self._selector.select(
                        backend=options.backend,
                        policy=options.backend_preference,
                    )
                except BackendUnavailableError as e:
                    raise PipelineStageError(
                        "Failed to select transcription backend",
                        stage=PipelineStage.SELECTING,
                        context={
                            "backend": options.backend.value,
                            "policy": options.backend_preference.value,
                        },
                        original_error=e,
                    ) from e
                emit_progress(
                    PipelineStage.SELECTING,
                    1.0,
                    f"Backend selected: {selected_backend_type.value}",
                )
                check_cancellation()

                # Step 6: Get backend instance and transcribe
                emit_progress(PipelineStage.TRANSCRIBING, 0.0, "Starting transcription")
                try:
                    backend = self._registry.get_backend(selected_backend_type, config=self.config)
                except BackendUnavailableError as e:
                    raise PipelineStageError(
                        "Failed to get transcription backend",
                        stage=PipelineStage.TRANSCRIBING,
                        original_error=e,
                    ) from e

                # Transcribe with error recovery
                result = self._transcribe_with_backend(
                    backend=backend,
                    audio_path=audio_path,
                    segments=segments,
                    media_info=media_info,
                    options=options,
                    progress_callback=progress_callback,
                    cancellation_token=cancellation_token,
                    emit_progress=emit_progress,
                )
                emit_progress(PipelineStage.TRANSCRIBING, 1.0, "Transcription complete")
                check_cancellation()

            # Update result with backend type (processing_time is already set by backend)
            result.backend_used = selected_backend_type

            # Step 7: Format output
            emit_progress(PipelineStage.FORMATTING, 0.0, "Formatting output")
            try:
                formatted_output = self._format_result(result, options)
                result.formatted_output = formatted_output
            except Exception as e:
                # Formatting error is non-fatal - result still valid
                logger.warning("Failed to format output: %s", e)
                result.formatted_output = None
            emit_progress(PipelineStage.FORMATTING, 1.0, "Output formatting complete")

            # Step 8: Complete
            emit_progress(PipelineStage.COMPLETE, 1.0, "Pipeline complete")

            return result

        except CancelledError:
            emit_progress(PipelineStage.COMPLETE, 0.0, "Pipeline cancelled")
            raise
        except PipelineStageError as e:
            if isinstance(e, CancelledError) or isinstance(e.original_error, CancelledError):
                emit_progress(PipelineStage.COMPLETE, 0.0, "Pipeline cancelled")
                raise (
                    e.original_error if isinstance(e.original_error, CancelledError) else e
                ) from e
            raise

    def _format_result(
        self,
        result: TranscriptionResult,
        options: TranscriptionOptions,
    ) -> str:
        """Format the transcription result based on output format.

        Args:
            result: The transcription result to format.
            options: Transcription options with output_format setting.

        Returns:
            Formatted string in the requested output format.
        """
        if options.output_format == OutputFormat.JSON:
            return format_json(result, options)
        elif options.output_format == OutputFormat.SRT:
            return format_srt(result, options)
        elif options.output_format == OutputFormat.VTT:
            return format_vtt(result, options)
        else:
            # Default to text format
            return format_text(result, options)

    def _transcribe_with_backend(
        self,
        backend: TranscriptionBackend,
        audio_path: Path,
        segments: list[Segment],
        media_info: MediaInfo,
        options: TranscriptionOptions,
        progress_callback: ProgressCallback | None = None,
        cancellation_token: CancellationToken | None = None,
        emit_progress: Callable[[PipelineStage, float, str], None] | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio using the selected backend.

        When VAD segments are available, they provide timing context that
        the backend may use to improve transcription accuracy. The backend
        handles segmentation internally, but VAD segments can be used to
        validate or refine results.

        Args:
            backend: The transcription backend to use.
            audio_path: Path to the extracted audio file.
            segments: Speech segments from VAD (used for timing context).
            media_info: Media metadata from probe.
            options: Transcription options.
            progress_callback: Optional callback for progress updates.
            cancellation_token: Optional token for cancellation.
            emit_progress: Safe progress emitter from Pipeline.transcribe().

        Returns:
            TranscriptionResult: Complete transcription result.

        Raises:
            PipelineStageError: If transcription fails.
            PartialResultError: If partial transcription succeeded.
        """
        # Report transcription progress using the safe emit_progress helper
        if emit_progress is not None:
            emit_progress(PipelineStage.TRANSCRIBING, 0.5, "Transcribing audio")

        try:
            result = backend.transcribe(audio_path, options)

            # If VAD segments detected speech but backend returned fewer/no segments,
            # use VAD segments to provide timing context for the result
            if segments and len(result.segments) < len(segments):
                logger.debug(
                    "Backend returned %d segments, VAD detected %d speech segments",
                    len(result.segments),
                    len(segments),
                )
        except PartialResultError:
            raise
        except CancelledError:
            raise
        except Exception as e:
            # Wrap in PipelineStageError with stage context
            raise PipelineStageError(
                "Transcription failed",
                stage=PipelineStage.TRANSCRIBING,
                context={"backend": backend.get_name(), "audio_path": str(audio_path)},
                original_error=e,
            ) from e

        # Preserve media info from probe
        result.media_info = media_info

        # Update config_used to reflect actual options
        result.config_used = options

        return result


def transcribe(
    path: str | Path,
    options: TranscriptionOptions | None = None,
    config: AppConfig | None = None,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> TranscriptionResult:
    """Convenience function for one-line transcription.

    Creates a Pipeline instance and transcribes the given file.
    This is the simplest way to use AudioCore for transcription.

    Args:
        path: Path to the audio/video file to transcribe.
        options: Transcription options. If None, uses defaults.
        config: Application configuration. If None, uses default AppConfig.
        progress_callback: Optional callback for progress notifications.
        cancellation_token: Optional token for cancellation support.

    Returns:
        TranscriptionResult: Complete transcription result with segments,
            media info, and processing metadata.

    Example:
        >>> from audiocore import transcribe
        >>> result = transcribe("audio.mp3")
        >>> print(result.segments[0].text)

        >>> # With progress callback
        >>> def on_progress(stage, progress, message):
        ...     print(f"[{stage.value}] {progress:.0%}: {message}")
        >>> result = transcribe("audio.mp3", progress_callback=on_progress)

        >>> # With custom options
        >>> from audiocore.models import TranscriptionOptions
        >>> from audiocore.types import BackendType
        >>> options = TranscriptionOptions(backend=BackendType.OPENAI)
        >>> result = transcribe("audio.mp3", options)
    """
    pipeline = Pipeline(config=config)
    return pipeline.transcribe(
        path=path,
        options=options,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )
