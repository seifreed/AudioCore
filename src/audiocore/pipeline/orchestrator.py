"""Pipeline orchestration for end-to-end transcription.

This module provides the main Pipeline class that coordinates the full
transcription workflow from media input to formatted output.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from audiocore.backends import BackendRegistry, BackendSelector
from audiocore.config import AppConfig
from audiocore.errors import MediaError
from audiocore.media import extract_audio, probe, temp_audio_file, validate_format_or_raise
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.output import format_json, format_text
from audiocore.pipeline.cancellation import CancellationToken, CancelledError
from audiocore.pipeline.progress import PipelineStage, ProgressCallback
from audiocore.types import BackendType, OutputFormat
from audiocore.vad import VADConfig, detect_speech

if TYPE_CHECKING:
    from audiocore.backends.base import TranscriptionBackend


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
        cancellation.

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
            TranscriptionError: If transcription fails.
            CancelledError: If cancellation is requested during execution.
        """
        start_time = time.time()
        path = Path(path)
        options = options or TranscriptionOptions()

        # Helper to emit progress safely
        def emit_progress(stage: PipelineStage, progress: float, message: str) -> None:
            if progress_callback is not None:
                progress_callback(stage, progress, message)

        # Helper to check cancellation safely
        def check_cancellation() -> None:
            if cancellation_token is not None:
                cancellation_token.check()

        try:
            # Step 1: Validate format
            emit_progress(PipelineStage.PROBING, 0.0, "Validating input format")
            validate_format_or_raise(path)
            check_cancellation()

            # Step 2: Probe media for metadata
            emit_progress(PipelineStage.PROBING, 0.0, "Starting media probe")
            media_info = probe(path)
            emit_progress(PipelineStage.PROBING, 1.0, "Media probe complete")
            check_cancellation()

            # Step 3-7: Process with temp file cleanup
            with temp_audio_file(suffix=".wav") as audio_path:
                # Step 3: Extract audio to temp file
                emit_progress(PipelineStage.EXTRACTING, 0.0, "Starting audio extraction")

                def extraction_progress(progress: float) -> None:
                    """Forward extraction progress to main callback."""
                    emit_progress(
                        PipelineStage.EXTRACTING, progress, f"Extracting audio: {progress:.0%}"
                    )

                extract_audio(path, audio_path, progress_callback=extraction_progress)
                emit_progress(PipelineStage.EXTRACTING, 1.0, "Audio extraction complete")
                check_cancellation()

                # Step 4: Run VAD to detect speech segments
                emit_progress(PipelineStage.VAD, 0.0, "Starting voice activity detection")
                vad_config = self.config.vad if hasattr(self.config, "vad") else VADConfig()
                segments = detect_speech(
                    audio_path=audio_path,
                    config=vad_config,
                    total_duration=media_info.duration,
                )
                emit_progress(PipelineStage.VAD, 1.0, "Voice activity detection complete")
                check_cancellation()

                # Step 5: Select backend
                emit_progress(PipelineStage.SELECTING, 0.0, "Selecting transcription backend")
                selected_backend_type = self._selector.select(
                    backend=options.backend,
                    policy=options.backend_preference,
                )
                emit_progress(
                    PipelineStage.SELECTING, 1.0, f"Backend selected: {selected_backend_type.value}"
                )
                check_cancellation()

                # Step 6: Get backend instance and transcribe
                emit_progress(PipelineStage.TRANSCRIBING, 0.0, "Starting transcription")
                backend = self._registry.get_backend(selected_backend_type)

                result = self._transcribe_with_backend(
                    backend=backend,
                    audio_path=audio_path,
                    segments=segments,
                    media_info=media_info,
                    options=options,
                    progress_callback=progress_callback,
                    cancellation_token=cancellation_token,
                )
                emit_progress(PipelineStage.TRANSCRIBING, 1.0, "Transcription complete")
                check_cancellation()

            # Calculate processing duration
            duration_seconds = time.time() - start_time

            # Update result with metadata
            result.duration_seconds = duration_seconds
            result.backend_used = selected_backend_type

            # Step 7: Format output
            emit_progress(PipelineStage.FORMATTING, 0.0, "Formatting output")
            formatted_output = self._format_result(result, options)
            result.formatted_output = formatted_output
            emit_progress(PipelineStage.FORMATTING, 1.0, "Output formatting complete")

            # Step 8: Complete
            emit_progress(PipelineStage.COMPLETE, 1.0, "Pipeline complete")

            return result

        except CancelledError:
            # Re-raise cancellation after cleanup (context manager handles temp files)
            emit_progress(PipelineStage.COMPLETE, 0.0, "Pipeline cancelled")
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
            Formatted string (text or JSON).
        """
        if options.output_format == OutputFormat.JSON:
            return format_json(result, options)
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
    ) -> TranscriptionResult:
        """Transcribe audio using the selected backend.

        For files with speech segments from VAD, this method transcribes
        the entire audio file and preserves the segment timing from VAD.
        The backend handles segmentation internally.

        Args:
            backend: The transcription backend to use.
            audio_path: Path to the extracted audio file.
            segments: Speech segments from VAD (used for timing context).
            media_info: Media metadata from probe.
            options: Transcription options.
            progress_callback: Optional callback for progress updates.
            cancellation_token: Optional token for cancellation.

        Returns:
            TranscriptionResult: Complete transcription result.
        """
        # Backend transcribes the full audio and handles internal segmentation
        result = backend.transcribe(audio_path, options)

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
