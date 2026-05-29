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
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from audiocore.backends.base import TranscriptionBackend
from audiocore.backends.faster_whisper import (
    ModelManager,
)
from audiocore.config.faster_whisper_config import FasterWhisperConfig
from audiocore.errors import BackendUnavailableError, TranscriptionError
from audiocore.models import (
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
    Word,
    floor_media_duration,
)
from audiocore.types import BackendType

if TYPE_CHECKING:
    from collections.abc import Iterator

    from audiocore.config import AppConfig

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

    def __init__(self, config: FasterWhisperConfig | AppConfig | None = None) -> None:
        """Initialize Faster-Whisper backend.

        Args:
            config: FasterWhisperConfig or AppConfig configuration. If AppConfig
                is provided, the faster_whisper sub-config is extracted. If
                FasterWhisperConfig is provided directly, it is used as-is.
                If not provided, defaults will be used.

        Note:
            Model is lazily loaded on first transcribe() call.
        """
        # Handle AppConfig passed from BackendRegistry
        from audiocore.config import AppConfig

        if isinstance(config, AppConfig):
            config = config.faster_whisper
        self.config: FasterWhisperConfig = config or FasterWhisperConfig()
        self._model: Any | None = None
        self._loaded_model_size: str | None = None
        self._model_lock = threading.Lock()
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

        Checks that both faster-whisper and ctranslate2 are installed.

        Returns:
            True if faster-whisper and ctranslate2 are installed, False otherwise.
        """
        try:
            import ctranslate2  # noqa: F401
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

        Note: faster-whisper (CTranslate2) only supports CUDA and CPU.
        MPS (Apple Silicon) GPU is NOT supported by CTranslate2.
        If MPS is detected or requested, falls back to CPU.

        Returns:
            Device string: "cuda" or "cpu".
        """
        device = self.config.device

        # Auto-detect device
        if device is None or (isinstance(device, str) and device.lower() == "auto"):
            from audiocore.backends.faster_whisper import get_best_device

            detected = get_best_device()
            # CTranslate2 doesn't support MPS, fallback to CPU
            if detected == "mps":
                logger.info(
                    "MPS detected but faster-whisper (CTranslate2) only supports CUDA/CPU. Using CPU."
                )
                return "cpu"
            return detected

        # Normalize device string
        device_lower = device.lower()

        # Validate device string
        if device_lower not in ("cuda", "mps", "cpu", "auto"):
            logger.warning(f"Unknown device '{device}', falling back to CPU")
            return "cpu"

        # Handle MPS: CTranslate2 doesn't support it, use CPU
        if device_lower == "mps":
            logger.info(
                "MPS requested but faster-whisper (CTranslate2) only supports CUDA/CPU. Using CPU."
            )
            return "cpu"

        # Handle CUDA: check if available
        if device_lower == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
                else:
                    logger.warning("CUDA requested but not available, falling back to CPU")
                    return "cpu"
            except ImportError:
                logger.warning("torch not installed, falling back to CPU")
                return "cpu"

        return device_lower

    def _load_model(self, model_size: str | None = None) -> Any:
        """Load model lazily.

        Downloads model if not cached, then loads into memory.
        If a different model_size is requested than what is currently loaded,
        the existing model is replaced.

        Thread-safe: acquires _model_lock to prevent concurrent model loading.

        Args:
            model_size: Optional model size override. If provided and different
                from the currently loaded model, a new model will be loaded.

        Returns:
            WhisperModel instance from faster-whisper.

        Raises:
            BackendUnavailableError: If faster-whisper not installed.
            TranscriptionError: If model download or loading fails.
        """
        # Determine effective model size
        effective_model_size = (
            model_size if model_size is not None else self.config.model_size.value
        )

        # Quick check without lock — if same model already loaded, return immediately
        if self._model is not None and self._loaded_model_size == effective_model_size:
            return self._model

        with self._model_lock:
            # Re-check after acquiring lock (double-checked locking)
            if self._model is not None and self._loaded_model_size == effective_model_size:
                return self._model

            # A different model was requested: drop the current one before reloading.
            if self._model is not None and self._loaded_model_size != effective_model_size:
                logger.info(
                    "Switching model from %s to %s",
                    self._loaded_model_size,
                    effective_model_size,
                )
                self._model = None

            if self._model is None:
                self._model = self._instantiate_model(effective_model_size)
                self._loaded_model_size = effective_model_size

            return self._model

    def _instantiate_model(self, model_size: str) -> Any:
        """Import faster-whisper, resolve the device, and construct the WhisperModel.

        Raises:
            BackendUnavailableError: If faster-whisper is not installed.
            TranscriptionError: If model download or construction fails.
        """
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
            ) from None

        device = self._get_device()
        compute_type = self.config.compute_type.value
        logger.info("Loading faster-whisper model: %s on %s", model_size, device)

        try:
            # WhisperModel downloads all necessary files automatically. Use
            # ModelManager's cache_dir so backend auto-downloads are visible to
            # ModelManager.is_model_downloaded().
            model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self._model_manager.cache_dir),
            )
        except Exception as e:
            raise TranscriptionError(
                f"Failed to load faster-whisper model: {e}",
                context={
                    "model": model_size,
                    "device": device,
                    "compute_type": compute_type,
                },
                suggestions=[
                    "Check internet connection for model download",
                    f"Try downloading model manually: huggingface-cli download guillaumekln/faster-whisper-{model_size}",
                    "Verify sufficient disk space",
                ],
            ) from e

        logger.info("Model %s loaded successfully", model_size)
        return model

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
        self._validate_audio_file(audio_path)

        params = self._build_transcribe_params(options)

        # Model size: options.model_size > config.model_size; a different size
        # forces a reload inside _load_model.
        if "model_size" in options.model_fields_set:
            effective_model_size = options.model_size
        else:
            effective_model_size = self.config.model_size
        model = self._load_model(model_size=effective_model_size.value)

        logger.debug(
            "Starting faster-whisper transcription for %s with params: %s",
            audio_path,
            params,
        )

        start_time = time.time()
        try:
            segments, info = model.transcribe(str(audio_path), **params)
            return self._build_result(segments, info, audio_path, options, time.time() - start_time)
        except BackendUnavailableError:
            raise
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

    def transcribe_stream(
        self, audio_path: Path | str, options: TranscriptionOptions
    ) -> Iterator[Segment]:
        """Yield segments lazily as faster-whisper decodes them.

        faster-whisper's ``model.transcribe`` returns a generator that decodes
        on demand, so each segment can be surfaced as soon as it is produced
        rather than waiting for the whole file.

        Raises:
            BackendUnavailableError: If faster-whisper is not installed.
            TranscriptionError: If transcription fails.
        """
        audio_path = Path(audio_path)
        self._validate_audio_file(audio_path)

        params = self._build_transcribe_params(options)
        if "model_size" in options.model_fields_set:
            effective_model_size = options.model_size
        else:
            effective_model_size = self.config.model_size
        model = self._load_model(model_size=effective_model_size.value)

        try:
            segments, _info = model.transcribe(str(audio_path), **params)
            for seg in segments:
                yield Segment(
                    start_time=seg.start,
                    end_time=seg.end,
                    text=seg.text.strip(),
                    words=self._extract_words(seg),
                )
        except BackendUnavailableError:
            raise
        except Exception as e:
            raise TranscriptionError(
                f"Faster-Whisper streaming transcription failed: {e}",
                context={"backend": "faster_whisper", "file_path": str(audio_path)},
                suggestions=[
                    "Check audio file format (mp3, wav, m4a, etc.)",
                    "Verify audio file is not corrupted",
                    "Try with different audio file",
                ],
            ) from e

    def _build_transcribe_params(self, options: TranscriptionOptions) -> dict[str, Any]:
        """Assemble faster-whisper transcribe() parameters from options and config.

        Language priority is options.language > config.language > None (auto-detect);
        decoding, thresholds, and advanced flags come from config.
        """
        params: dict[str, Any] = {"task": options.task.value}
        if options.language:
            params["language"] = options.language
        elif self.config.language:
            params["language"] = self.config.language

        params["beam_size"] = self.config.beam_size
        params["best_of"] = self.config.best_of
        params["patience"] = self.config.patience
        params["temperature"] = self.config.temperature
        params["compression_ratio_threshold"] = self.config.compression_ratio_threshold
        params["log_prob_threshold"] = self.config.log_prob_threshold
        params["no_speech_threshold"] = self.config.no_speech_threshold
        params["condition_on_previous_text"] = self.config.condition_on_previous_text
        # A caller's explicit options.word_timestamps overrides the backend config.
        params["word_timestamps"] = (
            options.word_timestamps
            if "word_timestamps" in options.model_fields_set
            else self.config.word_timestamps
        )
        params["vad_filter"] = self.config.vad_filter
        if self.config.initial_prompt:
            params["initial_prompt"] = self.config.initial_prompt
        return params

    @staticmethod
    def _extract_words(segment: Any) -> list[Word] | None:
        """Normalize a faster-whisper segment's word timestamps into Word models.

        Returns None when word timestamps were not requested (``segment.words``
        is None). faster-whisper exposes each word as ``word``/``start``/``end``/
        ``probability``; tiny negative floats are clamped to keep the model's
        non-negativity contract, and a word's end is floored to its start.
        """
        raw_words = getattr(segment, "words", None)
        if not raw_words:
            return None
        words: list[Word] = []
        for raw in raw_words:
            start = max(0.0, float(raw.start))
            end = max(start, float(raw.end))
            probability = getattr(raw, "probability", None)
            confidence = min(1.0, max(0.0, float(probability))) if probability is not None else None
            words.append(
                Word(
                    word=raw.word,
                    start_time=start,
                    end_time=end,
                    confidence=confidence,
                )
            )
        return words or None

    def _build_result(
        self,
        segments: Any,
        info: Any,
        audio_path: Path,
        options: TranscriptionOptions,
        processing_time_seconds: float,
    ) -> TranscriptionResult:
        """Convert faster-whisper output into a TranscriptionResult."""
        from audiocore.models import MediaInfo

        segment_list: list[Segment] = [
            Segment(
                start_time=seg.start,
                end_time=seg.end,
                text=seg.text.strip(),
                words=self._extract_words(seg),
            )
            for seg in segments
        ]

        duration = info.duration if hasattr(info, "duration") and info.duration else 0.0
        media_duration = floor_media_duration(duration)
        media_info = MediaInfo(
            duration=media_duration,
            format=audio_path.suffix.lstrip("."),
        )

        result = TranscriptionResult(
            segments=segment_list,
            media_info=media_info,
            config_used=options,
            processing_time_seconds=processing_time_seconds,
            backend_used=BackendType.FASTER_WHISPER,
        )
        logger.debug(
            "Faster-whisper transcription complete for %s: %d segments, %.2fs processing time",
            audio_path,
            len(segment_list),
            processing_time_seconds,
        )
        return result
