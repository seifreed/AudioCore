"""Silero VAD implementation for voice activity detection.

This module provides a thread-safe, lazy-loading wrapper around the Silero VAD model
for detecting speech segments in audio files.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import scipy.io.wavfile as wavfile
import torch
from torch import nn

from audiocore.errors import InvalidInputError, VADError
from audiocore.vad.config import VADConfig

if TYPE_CHECKING:
    from collections.abc import Iterator

    from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Full-scale divisors for normalizing integer PCM samples to float [-1, 1].
_INT16_FULL_SCALE = 32768.0
_INT32_FULL_SCALE = 2147483648.0
_UINT8_MIDPOINT = 128.0
_UINT16_MIDPOINT = 32768.0


class _SpeechSegmenter:
    """Builds speech segments from a stream of per-chunk speech probabilities.

    Applies hysteresis (enter at speech_threshold, exit at silence_threshold)
    and only closes a segment once silence has lasted min_silence_duration_ms.
    Raw detections are emitted as-is; minimum-duration handling is left to
    downstream segment processing.
    """

    def __init__(self, config: VADConfig) -> None:
        self._speech_threshold = config.speech_threshold
        self._silence_threshold = config.silence_threshold
        self._min_silence_s = config.min_silence_duration_ms / 1000.0
        self._segments: list[tuple[float, float, float]] = []
        self._in_speech = False
        self._speech_start: float | None = None
        self._confidences: list[float] = []
        self._silence_start: float | None = None

    def feed(self, current_time: float, speech_prob: float) -> None:
        """Advance the state machine with one chunk's speech probability."""
        threshold = self._silence_threshold if self._in_speech else self._speech_threshold
        is_speech = speech_prob >= threshold

        if is_speech and not self._in_speech:
            self._in_speech = True
            self._speech_start = current_time
            self._confidences = [speech_prob]
            self._silence_start = None
        elif is_speech and self._in_speech:
            self._confidences.append(speech_prob)
            self._silence_start = None
        elif not is_speech and self._in_speech:
            # Potential exit: require a minimum run of silence before closing.
            if self._silence_start is None:
                self._silence_start = current_time
            if current_time - self._silence_start >= self._min_silence_s:
                self._close_segment(self._silence_start)

    def finalize(self, end_time: float) -> list[tuple[float, float, float]]:
        """Close any segment still open at end_time and return all segments."""
        if self._in_speech and self._speech_start is not None and end_time - self._speech_start > 0:
            self._segments.append((self._speech_start, end_time, float(np.mean(self._confidences))))
        return self._segments

    def _close_segment(self, end_time: float) -> None:
        """Append the current speech run ending at end_time, then reset state."""
        if end_time - (self._speech_start or 0.0) > 0:
            self._segments.append(
                (self._speech_start or 0.0, end_time, float(np.mean(self._confidences)))
            )
        self._in_speech = False
        self._speech_start = None
        self._confidences = []
        self._silence_start = None


class SileroVAD:
    """Silero VAD model wrapper with lazy loading and thread-safe caching.

    This class provides a thread-safe singleton pattern for the Silero VAD model,
    ensuring it's only loaded once and reused across all instances.

    The model is loaded lazily on first use via torch.hub, with fallback to local
    cache if network is unavailable.

    Thread Safety:
        The model instance is a singleton shared across threads. Inference is
        serialized via _inference_lock to prevent concurrent model.reset_states()
        and model() calls from corrupting results.

    Attributes:
        _model: Class-level singleton model instance (None until loaded).
        _lock: Thread lock for thread-safe model loading.
        _sample_rate: Required sample rate for Silero (16000 Hz).

    Example:
        >>> vad = SileroVAD()
        >>> segments = vad.detect_file("audio.wav")
        >>> for start, end, conf in segments:
        ...     print(f"Speech: {start:.2f}s - {end:.2f}s (confidence: {conf:.2f})")
    """

    _model: nn.Module | None = None
    _lock: threading.Lock = threading.Lock()
    _inference_lock: threading.Lock = threading.Lock()
    _sample_rate: int = 16000

    def __init__(self, config: VADConfig | None = None) -> None:
        """Initialize SileroVAD instance.

        Args:
            config: Optional VAD configuration. Uses defaults if not provided.
        """
        self.config = config or VADConfig()

    @classmethod
    def _load_model(cls, timeout_seconds: int = 300) -> nn.Module:
        """Load the Silero VAD model with fallback to local cache.

        Attempts to load model from torch.hub first, then falls back to
        local cache if network is unavailable.

        Args:
            timeout_seconds: Timeout for model download in seconds (default: 300s / 5min).

        Returns:
            Loaded Silero VAD model.

        Raises:
            VADError: If model cannot be loaded from torch.hub or local cache.
        """
        try:
            return cls._download_model_with_timeout(timeout_seconds)
        except TimeoutError as timeout_exc:
            cached = cls._load_from_cache()
            if cached is not None:
                return cached
            raise VADError(
                message=f"Silero VAD model download timed out after {timeout_seconds} seconds",
                context={"timeout_seconds": timeout_seconds},
                suggestions=[
                    "Check internet connection and try again",
                    "Download model manually from https://github.com/snakers4/silero-vad",
                    "Increase timeout by passing timeout_seconds parameter",
                    "Use whole-file transcription without VAD segmentation",
                ],
            ) from timeout_exc
        except ImportError as import_error:
            raise VADError(
                message="torch is not installed, which is required for Silero VAD",
                context={"import_error": str(import_error)},
                suggestions=[
                    "Install torch: pip install torch",
                    "Or use whole-file transcription without VAD segmentation",
                ],
            ) from import_error
        except Exception as hub_error:
            cached = cls._load_from_cache()
            if cached is not None:
                return cached
            raise VADError(
                message="Failed to load Silero VAD model",
                context={
                    "hub_error": str(hub_error),
                    "cache_dir": str(cls._silero_cache_dir()),
                },
                suggestions=[
                    "Check internet connection for initial model download",
                    "Ensure torch is installed correctly: pip install torch",
                    "Try downloading model manually from https://github.com/snakers4/silero-vad",
                    "Use whole-file transcription without VAD segmentation",
                ],
            ) from hub_error

    @classmethod
    def _download_model_with_timeout(cls, timeout_seconds: int) -> nn.Module:
        """Download the Silero VAD model from torch.hub with a hard timeout.

        Raises:
            TimeoutError: If the download exceeds timeout_seconds.
        """
        import concurrent.futures

        def _download_from_hub() -> nn.Module:
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
            model.eval()
            return model

        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="silero-download"
        )
        future = executor.submit(_download_from_hub)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(
                f"Model download timed out after {timeout_seconds} seconds"
            ) from None
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _silero_cache_dir() -> Path:
        """Return the platform-specific torch.hub cache directory for Silero VAD."""
        import os
        import sys

        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            return Path(os.path.join(base, "torch", "hub", "snakers4_silero-vad_master"))
        return Path(os.path.expanduser("~/.cache/torch/hub/snakers4_silero-vad_master/"))

    @classmethod
    def _load_from_cache(cls) -> nn.Module | None:
        """Load Silero VAD from the local torch.hub cache, or None if unavailable.

        A cache load that raises is logged and treated as unavailable so the
        caller can surface the primary download failure instead.
        """
        cache_dir = cls._silero_cache_dir()
        if not cache_dir.exists():
            return None
        try:
            model_path = cache_dir / "files" / "silero_vad.jit"
            if not model_path.exists():
                return None
            loaded = torch.jit.load(str(model_path))
            loaded.eval()
            return loaded
        except Exception as cache_error:
            logger.warning(f"Failed to load Silero VAD from local cache: {cache_error}")
            return None

    @classmethod
    def get_model(cls) -> nn.Module:
        """Get the Silero VAD model, loading it lazily on first call.

        Thread-safe method that ensures the model is only loaded once.

        Returns:
            Silero VAD model instance.

        Raises:
            VADError: If model loading fails.
        """
        if cls._model is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._model is None:
                    cls._model = cls._load_model()
        return cls._model

    def _prepare_model(self) -> nn.Module:
        """Get the model with reset state for processing a new audio file.

        Resets the model's internal state before each file to prevent
        state accumulation across files. The model is a singleton shared
        across threads, so concurrent access requires external synchronization.

        Returns:
            Silero VAD model instance with reset state.
        """
        model = self.get_model()
        model.reset_states()
        return model

    def reset_state(self) -> None:
        """Reset the VAD model state for processing new audio.

        Should be called before processing a new audio file to reset
        internal state. Acquires inference lock to prevent corrupting
        ongoing inference in multi-threaded contexts.
        """
        with self._inference_lock:
            model = self.get_model()
            model.reset_states()

    def _load_audio(self, audio_path: Path | str) -> tuple[NDArray[np.float32], int]:
        """Load audio from WAV file and convert to required format.

        Converts stereo to mono, normalizes to float32, and validates sample rate.

        Args:
            audio_path: Path to WAV file.

        Returns:
            Tuple of (audio_data, sample_rate) where audio_data is float32 array.

        Raises:
            VADError: If sample rate is not 16kHz.
            FileNotFoundError: If audio file does not exist.
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise InvalidInputError(
                f"Audio file not found: {audio_path}",
                context={"file_path": str(audio_path)},
                suggestions=[
                    "Verify the file path is correct",
                    "Check the file exists",
                ],
            )
        if not audio_path.is_file():
            raise InvalidInputError(
                f"Audio path is not a file: {audio_path}",
                context={"file_path": str(audio_path)},
                suggestions=[
                    "Provide an audio file path, not a directory",
                    "Verify the file path is correct",
                ],
            )

        # Read WAV file
        sample_rate, data = wavfile.read(str(audio_path))

        # Validate sample rate (Silero requires 16kHz)
        if sample_rate != self._sample_rate:
            raise VADError(
                message=f"Invalid sample rate: {sample_rate}Hz. Silero VAD requires 16kHz audio.",
                context={
                    "file_path": str(audio_path),
                    "actual_rate": sample_rate,
                    "required_rate": self._sample_rate,
                },
                suggestions=[
                    f"Convert audio to 16kHz using ffmpeg: ffmpeg -i {audio_path} -ar 16000 output.wav",
                    "Use audiocore.media.extract_audio to convert audio to required format",
                ],
            )

        if data.size == 0:
            return data.astype(np.float32).flatten(), sample_rate

        data = self._normalize_to_float32(data)

        # Convert stereo to mono by averaging channels
        if len(data.shape) > 1 and data.shape[1] > 1:
            data = np.mean(data, axis=1)

        # Flatten if needed (ensure 1D array)
        data = data.flatten()

        return data, sample_rate

    @staticmethod
    def _normalize_to_float32(data: NDArray[Any]) -> NDArray[np.float32]:
        """Convert raw WAV samples to float32 normalized to [-1, 1].

        Integer PCM types are scaled by their full-scale divisor; float and
        unknown types are cast and clamped only if they exceed unit range.
        """
        if data.dtype == np.int16:
            return data.astype(np.float32) / _INT16_FULL_SCALE
        if data.dtype == np.int32:
            return data.astype(np.float32) / _INT32_FULL_SCALE
        if data.dtype == np.uint8:
            return (data.astype(np.float32) - _UINT8_MIDPOINT) / _UINT8_MIDPOINT
        if data.dtype == np.uint16:
            return (data.astype(np.float32) - _UINT16_MIDPOINT) / _UINT16_MIDPOINT

        # float32/float64 or unknown: cast, then clamp only if out of [-1, 1]
        floats = data.astype(np.float32)
        max_val = float(np.max(np.abs(floats)))
        if max_val > 1.0:
            logger.warning(f"Audio data exceeds [-1, 1] range (max={max_val:.2f}), normalizing")
            floats = floats / max_val
        return floats

    def detect_audio(
        self,
        audio_data: NDArray[np.floating[Any]],
        sample_rate: int,
        config: VADConfig | None = None,
    ) -> list[tuple[float, float, float]]:
        """Detect speech segments in audio data.

        Processes audio in 512-sample chunks (optimal for Silero) and returns
        segments with start time, end time, and confidence.

        Args:
            audio_data: Audio samples as float array (normalized to [-1, 1]).
            sample_rate: Sample rate of audio (must be 16000 for Silero).
            config: Optional VAD configuration. Uses defaults if not provided.

        Returns:
            List of (start_time, end_time, confidence) tuples where times are in seconds
            and confidence is the mean probability across chunk samples.

        Raises:
            VADError: If sample rate is not 16kHz or processing fails.
        """
        # Validate sample rate
        if sample_rate != self._sample_rate:
            raise VADError(
                message=f"Invalid sample rate: {sample_rate}Hz. Silero VAD requires 16kHz audio.",
                context={
                    "actual_rate": sample_rate,
                    "required_rate": self._sample_rate,
                },
                suggestions=[
                    "Convert audio to 16kHz before VAD processing",
                    "Use audiocore.media.extract_audio to convert audio",
                ],
            )

        # Use provided config or create default
        if config is None:
            config = self.config

        # Get thread-local model instance with isolated state
        with self._inference_lock:
            model = self._prepare_model()
            # window_size_samples from config (default 512, optimal for Silero)
            chunk_size = config.window_size_samples
            segmenter = _SpeechSegmenter(config)
            for current_time, speech_prob in self._iter_speech_probs(
                model, audio_data, sample_rate, chunk_size
            ):
                segmenter.feed(current_time, speech_prob)
            return segmenter.finalize(len(audio_data) / sample_rate)

    def _iter_speech_probs(
        self,
        model: nn.Module,
        audio_data: NDArray[np.floating[Any]],
        sample_rate: int,
        chunk_size: int,
    ) -> Iterator[tuple[float, float]]:
        """Yield (chunk_start_time, speech_probability) for each audio chunk.

        The final partial chunk is zero-padded for consistent model input.
        """
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i : min(i + chunk_size, len(audio_data))]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)), mode="constant")
            chunk_tensor = torch.from_numpy(chunk)
            with torch.no_grad():
                speech_prob = model(chunk_tensor, sample_rate).item()
            yield i / sample_rate, speech_prob

    def detect_file(
        self,
        audio_path: Path | str,
        config: VADConfig | None = None,
    ) -> list[tuple[float, float, float]]:
        """Detect speech segments in an audio file.

        Loads the WAV file and processes it for speech detection.

        Args:
            audio_path: Path to WAV audio file (must be 16kHz).
            config: Optional VAD configuration.

        Returns:
            List of (start_time, end_time, confidence) tuples.

        Raises:
            VADError: If audio cannot be loaded or processed.
            InvalidInputError: If audio file does not exist.
        """
        # Load audio file
        audio_data, sample_rate = self._load_audio(audio_path)

        # Process for speech detection
        return self.detect_audio(audio_data, sample_rate, config)
