"""Pipeline orchestration for end-to-end transcription.

This module provides the main Pipeline class that coordinates the full
transcription workflow from media input to formatted output.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from audiocore.backends import BackendRegistry, BackendSelector
from audiocore.config import AppConfig
from audiocore.errors import MediaError
from audiocore.media import extract_audio, probe, temp_audio_file, validate_format_or_raise
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType
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

    Example:
        >>> pipeline = Pipeline()
        >>> result = pipeline.transcribe("audio.mp3")
        >>> print(result.segments[0].text)

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

        Temporary files are automatically cleaned up even on failure.

        Args:
            path: Path to the audio/video file to transcribe.
            options: Transcription options. If None, uses defaults.

        Returns:
            TranscriptionResult: Complete transcription result with segments,
                media info, and processing metadata.

        Raises:
            MediaFormatError: If the input format is not supported.
            MediaError: If media probing or extraction fails.
            VADError: If VAD processing fails.
            BackendUnavailableError: If no backend is available.
            TranscriptionError: If transcription fails.
        """
        start_time = time.time()
        path = Path(path)
        options = options or TranscriptionOptions()

        # Step 1: Validate format
        validate_format_or_raise(path)

        # Step 2: Probe media for metadata
        media_info = probe(path)

        # Step 3-6: Process with temp file cleanup
        with temp_audio_file(suffix=".wav") as audio_path:
            # Step 3: Extract audio to temp file
            extract_audio(path, audio_path)

            # Step 4: Run VAD to detect speech segments
            vad_config = self.config.vad if hasattr(self.config, "vad") else VADConfig()
            segments = detect_speech(
                audio_path=audio_path,
                config=vad_config,
                total_duration=media_info.duration,
            )

            # Step 5: Select backend
            selected_backend_type = self._selector.select(
                backend=options.backend,
                policy=options.backend_preference,
            )

            # Step 6: Get backend instance
            backend = self._registry.get_backend(selected_backend_type)

            # Step 7: Transcribe and merge results
            result = self._transcribe_with_backend(
                backend=backend,
                audio_path=audio_path,
                segments=segments,
                media_info=media_info,
                options=options,
            )

        # Calculate processing duration
        duration_seconds = time.time() - start_time

        # Update result with metadata
        result.duration_seconds = duration_seconds
        result.backend_used = selected_backend_type

        return result

    def _transcribe_with_backend(
        self,
        backend: TranscriptionBackend,
        audio_path: Path,
        segments: list[Segment],
        media_info: MediaInfo,
        options: TranscriptionOptions,
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
) -> TranscriptionResult:
    """Convenience function for one-line transcription.

    Creates a Pipeline instance and transcribes the given file.
    This is the simplest way to use AudioCore for transcription.

    Args:
        path: Path to the audio/video file to transcribe.
        options: Transcription options. If None, uses defaults.
        config: Application configuration. If None, uses default AppConfig.

    Returns:
        TranscriptionResult: Complete transcription result with segments,
            media info, and processing metadata.

    Example:
        >>> from audiocore import transcribe
        >>> result = transcribe("audio.mp3")
        >>> print(result.segments[0].text)

        >>> # With custom options
        >>> from audiocore.models import TranscriptionOptions
        >>> from audiocore.types import BackendType
        >>> options = TranscriptionOptions(backend=BackendType.OPENAI)
        >>> result = transcribe("audio.mp3", options)
    """
    pipeline = Pipeline(config=config)
    return pipeline.transcribe(path=path, options=options)
