"""Faster-Whisper local transcription backend implementation.

This module provides the faster-whisper integration for local audio/video
transcription using CTranslate2-optimized Whisper models. It implements
the TranscriptionBackend interface with automatic model management,
GPU acceleration, and comprehensive error handling.

Key Features:
- Lazy model loading (model loaded on first transcription)
- Automatic GPU device selection (CUDA > MPS > CPU)
- HuggingFace Hub model management
- Comprehensive error mapping to AudioCore exceptions
- Support for all faster-whisper decoding parameters

Example:
    >>> from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
    >>> from audiocore.config.faster_whisper_config import FasterWhisperConfig
    >>> config = FasterWhisperConfig(model_size="base", device="cuda")
    >>> backend = FasterWhisperBackend(config=config)
    >>> result = backend.transcribe("audio.mp3", TranscriptionOptions())
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from audiocore.backends.base import TranscriptionBackend
from audiocore.backends.faster_whisper import (
    ModelManager,
    get_best_device,
)
from audiocore.config.faster_whisper_config import ComputeType, FasterWhisperConfig
from audiocore.errors import BackendUnavailableError, TranscriptionError
from audiocore.models import Segment, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType

logger = logging.getLogger(__name__)


class FasterWhisperBackend(TranscriptionBackend):
    """Faster-Whisper local transcription backend.

    Implements the TranscriptionBackend interface using faster-whisper
    (CTranslate2-optimized Whisper models) for local transcription.
    Provides automatic model management, GPU acceleration, and
    comprehensive error handling.

    Attributes:
        backend_type: Returns BackendType.FASTER_WHISPER.
        _model: Lazily-initialized faster-whisper model instance.
        _model_manager: ModelManager instance for model downloading.
        config: FasterWhisperConfig configuration instance.

    Example:
        >>> from audiocore.config.faster_whisper_config import FasterWhisperConfig
        >>> config = FasterWhisperConfig(model_size="base")
        >>> backend = FasterWhisperBackend(config=config)
        >>> if backend.is_available():
        ...     result = backend.transcribe("audio.mp3", TranscriptionOptions())
        ...     print(result.segments[0].text)

    Note:
        - Model is downloaded on first transcription (lazy loading)
        - GPU device is auto-detected (CUDA > MPS > CPU)
        - All faster-whisper exceptions are mapped to AudioCore exceptions
    """

    def __init__(self, config: FasterWhisperConfig | None = None) -> None:
        """Initialize Faster-Whisper backend.

        Args:
            config: FasterWhisperConfig configuration. If not provided,
                defaults will be used (ModelSize.BASE, auto device, etc.).

        Note:
            Model is lazily loaded on first transcribe() call.
        """
        self.config = config or FasterWhisperConfig()
        self._model: Any | None = None
        self._model_manager = ModelManager()

        logger.debug(
            "FasterWhisperBackend initialized with model_size=%s, device=%s",
            self.config.model_size.value,
            self.config.device or "auto",
        )

    @property
    def backend_type(self) -> BackendType:
        """Return the backend type identifier.

        Returns:
            BackendType.FASTER_WHISPER enum value.
        """
        return BackendType.FASTER_WHISPER

    def get_name(self) -> str:
        """Return human-readable backend name.

        Returns:
            "Faster-Whisper (local)" display name.
        """
        return "Faster-Whisper (local)"

    def is_available(self) -> bool:
        """Check if faster-whisper backend is available.

        Checks that faster-whisper package is installed.

        Returns:
            True if faster-whisper is installed, False otherwise.
        """
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False

    def get_model_options(self) -> list[str]:
        """Return list of available model names.

        Returns:
            List of model size names (tiny, base, small, medium, large).
        """
        return FasterWhisperConfig.get_available_models()

    def _get_device(self) -> str:
        """Resolve device from config or auto-detect.

        Returns:
            Device string: "cuda", "mps", or "cpu".
        """
        if self.config.device is None or self.config.device.lower() == "auto":
            return get_best_device()
        return self.config.device.lower()

    def _load_model(self) -> Any:
        """Load model lazily.

        Downloads model if not cached, then loads into memory.

        Returns:
            WhisperModel instance from faster-whisper.

        Raises:
            BackendUnavailableError: If faster-whisper not installed.
            TranscriptionError: If model download or loading fails.
        """
        if self._model is None:
            # Validate faster-whisper is installed
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise BackendUnavailableError(
                    "faster-whisper package not installed",
                    context={"backend": "faster_whisper"},
                    suggestions=[
                        "Install faster-whisper: pip install faster-whisper",
                        "Or install audiocore with extras: pip install audiocore[faster-whisper]",
                    ],
                )

            # Get device and compute type
            device = self._get_device()
            compute_type = self.config.compute_type.value

            # Download model from HuggingFace Hub
            model_name = self.config.model_size.value
            logger.info("Loading faster-whisper model: %s on %s", model_name, device)

            try:
                # Download model (uses cache if already downloaded)
                model_path = self._model_manager.download_model(model_name)

                # Load model into memory
                logger.debug(
                    "Loading model from %s with compute_type=%s",
                    model_path,
                    compute_type,
                )
                self._model = WhisperModel(
                    str(model_path.parent),  # WhisperModel needs directory
                    device=device,
                    compute_type=compute_type,
                )

                logger.info("Model %s loaded successfully", model_name)

            except Exception as e:
                raise TranscriptionError(
                    f"Failed to load faster-whisper model: {e}",
                    context={"model": model_name, "device": device, "compute_type": compute_type},
                    suggestions=[
                        "Check internet connection for model download",
                        f"Try downloading model manually: huggingface-cli download guillaumekln/faster-whisper-{model_name}",
                        "Verify sufficient disk space",
                    ],
                ) from e

        return self._model

    def transcribe(
        self, audio_path: Path | str, options: TranscriptionOptions
    ) -> TranscriptionResult:
        """Transcribe an audio/video file using faster-whisper.

        Args:
            audio_path: Path to the audio/video file to transcribe.
            options: Transcription configuration options.

        Returns:
            TranscriptionResult with segments and metadata.

        Raises:
            BackendUnavailableError: If faster-whisper not installed.
            TranscriptionError: If transcription fails.

        Note:
            Model is loaded on first call (lazy loading).
        """
        audio_path = Path(audio_path)

        # Validate file exists
        if not audio_path.exists():
            raise TranscriptionError(
                f"Audio file not found: {audio_path}",
                context={"file_path": str(audio_path), "backend": "faster_whisper"},
                suggestions=[
                    "Verify the file path is correct",
                    "Check the file exists",
                ],
            )

        # Load model lazily
        model = self._load_model()

        # Build transcription parameters from config
        # Language: options.language > config.language > None (auto-detect)
        params: dict[str, Any] = {}

        if options.language:
            params["language"] = options.language
        elif self.config.language:
            params["language"] = self.config.language

        # Decoding parameters from config
        params["beam_size"] = self.config.beam_size
        params["best_of"] = self.config.best_of
        params["patience"] = self.config.patience
        params["temperature"] = self.config.temperature

        # Thresholds from config
        params["compression_ratio_threshold"] = self.config.compression_ratio_threshold
        params["log_prob_threshold"] = self.config.log_prob_threshold
        params["no_speech_threshold"] = self.config.no_speech_threshold

        # Advanced options from config
        params["condition_on_previous_text"] = self.config.condition_on_previous_text
        params["word_timestamps"] = self.config.word_timestamps
        params["vad_filter"] = self.config.vad_filter

        # Optional initial_prompt
        if self.config.initial_prompt:
            params["initial_prompt"] = self.config.initial_prompt

        logger.debug(
            "Starting faster-whisper transcription for %s with params: %s",
            audio_path,
            params,
        )

        try:
            # Perform transcription
            segments, info = model.transcribe(str(audio_path), **params)

            # Convert segments to list
            segment_list: list[Segment] = []
            for seg in segments:
                segment_list.append(
                    Segment(
                        start_time=seg.start,
                        end_time=seg.end,
                        text=seg.text.strip(),
                    )
                )

            # Get duration from info
            duration = info.duration if hasattr(info, "duration") and info.duration else 0.0

            # Use minimum duration if zero (MediaInfo requires duration > 0)
            media_duration = duration if duration > 0 else 0.01

            # Build media info
            from audiocore.models import MediaInfo

            media_info = MediaInfo(
                duration=media_duration,
                format=audio_path.suffix.lstrip("."),
            )

            result = TranscriptionResult(
                segments=segment_list,
                media_info=media_info,
                config_used=options,
                duration_seconds=duration,
                backend_used=BackendType.FASTER_WHISPER,
            )

            logger.debug(
                "Faster-whisper transcription complete for %s: %d segments, %.2fs duration",
                audio_path,
                len(segment_list),
                duration,
            )

            return result

        except Exception as e:
            raise TranscriptionError(
                f"Faster-Whisper transcription failed: {e}",
                context={"backend": "faster_whisper", "file_path": str(audio_path)},
                suggestions=[
                    "Check audio file format (mp3, wav, m4a, etc.)",
                    "Verify audio file is not corrupted",
                    "Try with different audio file",
                ],
            ) from e
