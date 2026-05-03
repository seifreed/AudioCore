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

from audiocore.errors import VADError
from audiocore.vad.config import VADConfig

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


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

        # Try torch hub first with thread-safe timeout
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="silero-download"
        )
        try:
            future = executor.submit(_download_from_hub)
            try:
                return future.result(timeout=timeout_seconds)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(
                    f"Model download timed out after {timeout_seconds} seconds"
                ) from None
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        except TimeoutError as timeout_exc:
            # Try local cache fallback after timeout
            import os
            import sys

            cache_fallback_error: Exception | None = None
            if sys.platform == "win32":
                base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
                cache_dir = os.path.join(base, "torch", "hub", "snakers4_silero-vad_master")
            else:
                cache_dir = os.path.expanduser("~/.cache/torch/hub/snakers4_silero-vad_master/")
            if Path(cache_dir).exists():
                try:
                    model_path = Path(cache_dir) / "files" / "silero_vad.jit"
                    if model_path.exists():
                        model = torch.jit.load(str(model_path))
                        model.eval()
                        return model
                except Exception as cache_error:
                    cache_fallback_error = cache_error
                    logger.warning(
                        f"Failed to load Silero VAD from cache after timeout: {cache_error}"
                    )
            raise VADError(
                message=f"Silero VAD model download timed out after {timeout_seconds} seconds",
                context={"timeout_seconds": timeout_seconds},
                suggestions=[
                    "Check internet connection and try again",
                    "Download model manually from https://github.com/snakers4/silero-vad",
                    "Increase timeout by passing timeout_seconds parameter",
                    "Use whole-file transcription without VAD segmentation",
                ],
            ) from (cache_fallback_error or timeout_exc)
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
            # Try local cache fallback
            import os
            import sys

            if sys.platform == "win32":
                base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
                cache_dir = os.path.join(base, "torch", "hub", "snakers4_silero-vad_master")
            else:
                cache_dir = os.path.expanduser("~/.cache/torch/hub/snakers4_silero-vad_master/")
            if Path(cache_dir).exists():
                try:
                    # Attempt to load from local cache
                    model_path = Path(cache_dir) / "files" / "silero_vad.jit"
                    if model_path.exists():
                        model = torch.jit.load(str(model_path))
                        model.eval()
                        return model
                except Exception as cache_error:
                    logger.warning(f"Failed to load Silero VAD from local cache: {cache_error}")

            # Both methods failed
            raise VADError(
                message="Failed to load Silero VAD model",
                context={
                    "hub_error": str(hub_error),
                    "cache_dir": cache_dir if "cache_dir" in locals() else "not found",
                },
                suggestions=[
                    "Check internet connection for initial model download",
                    "Ensure torch is installed correctly: pip install torch",
                    "Try downloading model manually from https://github.com/snakers4/silero-vad",
                    "Use whole-file transcription without VAD segmentation",
                ],
            ) from hub_error

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
            assert cls._lock is not None
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
        internal state.
        """
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
            from audiocore.errors import InvalidInputError

            raise InvalidInputError(
                f"Audio file not found: {audio_path}",
                context={"file_path": str(audio_path)},
                suggestions=[
                    "Verify the file path is correct",
                    "Check the file exists",
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

        # Convert to float32 normalized to [-1, 1]
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        elif data.dtype == np.uint8:
            data = (data.astype(np.float32) - 128) / 128.0
        elif data.dtype == np.float32 or data.dtype == np.float64:
            data = data.astype(np.float32)
            # Validate float32 data is in [-1, 1] range
            max_val = np.max(np.abs(data))
            if max_val > 1.0:
                logger.warning(f"Audio data exceeds [-1, 1] range (max={max_val:.2f}), normalizing")
                data = data / max_val
        else:
            data = data.astype(np.float32)

        # Convert stereo to mono by averaging channels
        if len(data.shape) > 1 and data.shape[1] > 1:
            data = np.mean(data, axis=1)

        # Flatten if needed (ensure 1D array)
        data = data.flatten()

        return data, sample_rate

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
            config = VADConfig()

        # Get thread-local model instance with isolated state
        with self._inference_lock:
            model = self._prepare_model()

            # Use window_size_samples from config (default 512, optimal for Silero)
            chunk_size = config.window_size_samples
            segments: list[tuple[float, float, float]] = []

            # Track speech state
            in_speech = False
            speech_start_time: float | None = None
            chunk_confidences: list[float] = []
            silence_start_time: float | None = None

            # Convert min_silence_duration from ms to seconds
            min_silence_duration_s = config.min_silence_duration_ms / 1000.0

            # Process each full chunk (skip partial chunks at the end)
            for i in range(0, len(audio_data), chunk_size):
                if i + chunk_size > len(audio_data):
                    break  # Skip partial chunk at end of audio
                chunk = audio_data[i : i + chunk_size]

                # Convert to torch tensor
                chunk_tensor = torch.from_numpy(chunk)

                # Get speech probability from Silero
                with torch.no_grad():
                    speech_prob = model(chunk_tensor, sample_rate).item()

                # Determine if we're in speech based on threshold
                current_time = i / sample_rate

                # Use speech_threshold for entering speech,
                # silence_threshold for exiting speech (hysteresis)
                if in_speech:
                    # Already in speech: exit only when prob drops below silence_threshold
                    is_speech = speech_prob >= config.silence_threshold
                else:
                    # Not in speech: enter only when prob exceeds speech_threshold
                    is_speech = speech_prob > config.speech_threshold

                # Track state transitions
                if is_speech and not in_speech:
                    # Entering speech
                    in_speech = True
                    speech_start_time = current_time
                    chunk_confidences = [speech_prob]
                    silence_start_time = None
                elif is_speech and in_speech:
                    # Continuing speech
                    chunk_confidences.append(speech_prob)
                    silence_start_time = None
                elif not is_speech and in_speech:
                    # Potential speech exit - check minimum silence duration
                    if silence_start_time is None:
                        silence_start_time = current_time

                    silence_duration = current_time - silence_start_time
                    if silence_duration >= min_silence_duration_s:
                        # Confirmed exit: silence is long enough
                        speech_duration = silence_start_time - (speech_start_time or 0.0)

                        # Only record if above minimum duration
                        if speech_duration >= config.min_segment_duration:
                            mean_confidence = float(np.mean(chunk_confidences))
                            segments.append(
                                (speech_start_time or 0.0, silence_start_time, mean_confidence)
                            )

                        # Reset speech tracking
                        in_speech = False
                        speech_start_time = None
                        chunk_confidences = []
                        silence_start_time = None

            # Handle case where audio ends during speech
            if in_speech and speech_start_time is not None:
                end_time = len(audio_data) / sample_rate
                speech_duration = end_time - speech_start_time

                if speech_duration >= config.min_segment_duration:
                    mean_confidence = float(np.mean(chunk_confidences))
                    segments.append((speech_start_time, end_time, mean_confidence))

            return segments

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
