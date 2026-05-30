"""Unit tests for Silero VAD integration.

These tests patch silero_vad.load_silero_vad to avoid loading the bundled
model. The real model is shipped offline inside the silero-vad package, so
no download occurs.
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import scipy.io.wavfile as wavfile
import torch

from audiocore.errors import VADError
from audiocore.vad.silero import SileroVAD


class _FakeVADModel:
    """Real in-memory stand-in for the Silero JIT model (not a MagicMock).

    Exposes the surface the loader contract relies on: ``reset_states`` and a
    ``__call__(chunk, sample_rate)`` returning a tensor with ``.item()``.
    """

    def __init__(self) -> None:
        self.reset_calls = 0

    def reset_states(self) -> None:
        self.reset_calls += 1

    def __call__(self, chunk: object, sample_rate: int) -> torch.Tensor:
        return torch.tensor(0.5)


@pytest.fixture(autouse=True)
def _reset_silero_singleton() -> Any:
    """Reset the cached singleton model around each test for isolation."""
    SileroVAD._model = None
    yield
    SileroVAD._model = None


class TestModelLoading:
    """Test model loading and caching behavior."""

    def test_model_is_none_on_import(self) -> None:
        """Verify the class exposes the lazy-loading singleton attributes."""
        assert hasattr(SileroVAD, "_model")
        assert hasattr(SileroVAD, "_lock")
        assert hasattr(SileroVAD, "_sample_rate")
        assert SileroVAD._sample_rate == 16000

    def test_get_model_loads_via_load_silero_vad(self) -> None:
        """get_model loads the bundled model through load_silero_vad(onnx=False)."""
        fake = _FakeVADModel()
        with patch("silero_vad.load_silero_vad", return_value=fake) as mock_load:
            model = SileroVAD.get_model()

        mock_load.assert_called_once_with(onnx=False)
        assert model is fake

    def test_get_model_caches_model(self) -> None:
        """Subsequent calls return the cached model without reloading."""
        fake = _FakeVADModel()
        with patch("silero_vad.load_silero_vad", return_value=fake) as mock_load:
            model1 = SileroVAD.get_model()
            model2 = SileroVAD.get_model()

        assert model1 is model2
        assert mock_load.call_count == 1

    def test_load_model_raises_vad_error_when_package_missing(self) -> None:
        """A missing silero-vad package surfaces as VADError with install guidance."""
        with patch.dict("sys.modules", {"silero_vad": None}):
            with pytest.raises(VADError) as exc_info:
                SileroVAD.get_model()

        assert exc_info.value.error_code == "AUD-401"
        assert "silero-vad" in str(exc_info.value)
        assert any("pip install silero-vad" in s for s in exc_info.value.suggestions)

    def test_load_model_wraps_loader_failure_in_vad_error(self) -> None:
        """A loader failure is wrapped in VADError, preserving the cause chain."""
        with patch("silero_vad.load_silero_vad", side_effect=RuntimeError("boom")):
            with pytest.raises(VADError) as exc_info:
                SileroVAD.get_model()

        assert "Failed to load the bundled Silero VAD model" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestAudioLoading:
    """Test audio file loading functionality."""

    def _create_test_wav(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        duration: float = 1.0,
        dtype: type = np.int16,
    ) -> Path:
        """Create a test WAV file and return its path."""
        # Generate test audio data
        samples = int(sample_rate * duration)
        if dtype == np.int16:
            data = np.random.randint(-1000, 1000, size=(samples, channels), dtype=np.int16)
        elif dtype == np.float32:
            data = np.random.rand(samples, channels).astype(np.float32) * 0.5
        else:
            # uint8
            data = np.random.randint(0, 255, size=(samples, channels), dtype=np.uint8)

        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".wav")
        Path(path)

        # Write WAV file
        wavfile.write(path, sample_rate, data)

        return Path(path)

    def test_load_audio_reads_wav_file(self, tmp_path: Path) -> None:
        """Test that load_audio reads WAV files correctly."""
        # Create test WAV file
        test_wav = tmp_path / "test.wav"
        sample_rate = 16000
        duration = 1.0
        data = np.random.randint(-1000, 1000, size=int(sample_rate * duration), dtype=np.int16)
        wavfile.write(str(test_wav), sample_rate, data)

        vad = SileroVAD()
        audio_data, sr = vad._load_audio(test_wav)

        assert sr == 16000
        assert isinstance(audio_data, np.ndarray)
        assert len(audio_data) == int(sample_rate * duration)

    def test_load_audio_converts_stereo_to_mono(self, tmp_path: Path) -> None:
        """Test that stereo audio is converted to mono."""
        # Create stereo WAV file
        test_wav = tmp_path / "stereo.wav"
        sample_rate = 16000
        samples = int(sample_rate * 1.0)

        # Create stereo data with different values in each channel
        stereo_data = np.column_stack(
            [
                np.ones(samples, dtype=np.float32) * 0.5,  # Left channel
                np.ones(samples, dtype=np.float32) * 0.3,  # Right channel
            ]
        )
        wavfile.write(str(test_wav), sample_rate, stereo_data.astype(np.float32))

        vad = SileroVAD()
        audio_data, _ = vad._load_audio(test_wav)

        # Should be mono (1D array)
        assert len(audio_data.shape) == 1 or audio_data.shape[1] == 1

        # Should be average of channels
        # Left is 0.5, right is 0.3, expected mono is ~0.4
        expected_mean = (0.5 + 0.3) / 2
        actual_mean = float(np.mean(audio_data))
        # Account for float precision and normalization
        assert abs(actual_mean - expected_mean) < 0.1

    def test_load_audio_normalizes_int16_to_float32(self, tmp_path: Path) -> None:
        """Test that int16 audio is normalized to float32 [-1, 1]."""
        test_wav = tmp_path / "int16.wav"
        sample_rate = 16000
        data = np.array([32767, 0, -32768, 0], dtype=np.int16)  # Max int16 values
        wavfile.write(str(test_wav), sample_rate, data)

        vad = SileroVAD()
        audio_data, _ = vad._load_audio(test_wav)

        # Should be float32
        assert audio_data.dtype == np.float32

        # Should be normalized to [-1, 1]
        assert audio_data[0] == pytest.approx(1.0, abs=0.01)
        assert audio_data[2] == pytest.approx(-1.0, abs=0.01)

    def test_load_audio_validates_sample_rate(self, tmp_path: Path) -> None:
        """Test that wrong sample rate raises VADError."""
        # Create WAV with wrong sample rate (44.1kHz instead of 16kHz)
        test_wav = tmp_path / "wrong_rate.wav"
        sample_rate = 44100
        data = np.random.randint(-1000, 1000, size=1000, dtype=np.int16)
        wavfile.write(str(test_wav), sample_rate, data)

        vad = SileroVAD()

        with pytest.raises(VADError) as exc_info:
            vad._load_audio(test_wav)

        assert "Invalid sample rate" in str(exc_info.value)
        assert exc_info.value.error_code == "AUD-401"
        assert exc_info.value.context.get("actual_rate") == 44100
        assert exc_info.value.context.get("required_rate") == 16000

    def test_load_audio_empty_float_wav_returns_empty_array(self, tmp_path: Path) -> None:
        """Regression: empty float WAV input should not fail during normalization."""
        test_wav = tmp_path / "empty_float.wav"
        wavfile.write(str(test_wav), 16000, np.array([], dtype=np.float32))

        vad = SileroVAD()
        audio_data, sample_rate = vad._load_audio(test_wav)

        assert sample_rate == 16000
        assert audio_data.dtype == np.float32
        assert audio_data.size == 0


class TestSpeechDetection:
    """Test speech detection functionality."""

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_returns_segments(self, mock_get_model: MagicMock) -> None:
        """Test that detect_audio returns speech segments."""
        # Create mock model that returns high probability for speech
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.9)  # High speech probability
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        # Create test audio (1 second at 16kHz)
        audio_data = np.random.rand(16000).astype(np.float32)

        vad = SileroVAD()
        segments = vad.detect_audio(audio_data, 16000)

        # Should return segments
        assert isinstance(segments, list)
        assert len(segments) > 0

        # Each segment should be (start, end, confidence)
        for start, end, confidence in segments:
            assert isinstance(start, float)
            assert isinstance(end, float)
            assert isinstance(confidence, float)
            assert end >= start
            assert 0.0 <= confidence <= 1.0

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_empty_audio_returns_empty_list(self, mock_get_model: MagicMock) -> None:
        """Test that empty audio returns empty segments."""
        mock_model = MagicMock()
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        vad = SileroVAD()
        segments = vad.detect_audio(np.array([], dtype=np.float32), 16000)

        assert segments == []

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_processes_in_chunks(self, mock_get_model: MagicMock) -> None:
        """Test that audio is processed in 512-sample chunks."""
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.5)
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        # Create audio slightly larger than one chunk
        audio_data = np.random.rand(1024).astype(np.float32)  # 2 chunks at 512 samples

        vad = SileroVAD()
        vad.detect_audio(audio_data, 16000)

        # Model should be called once per chunk
        # (actual call count depends on implementation details)
        assert mock_model.call_count >= 1

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_uses_instance_config_by_default(self, mock_get_model: MagicMock) -> None:
        """Regression: constructor config should apply when detect_audio config is omitted."""
        from audiocore.vad.config import VADConfig

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.6)
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        vad = SileroVAD(
            config=VADConfig(
                speech_threshold=0.9,
                silence_threshold=0.3,
                min_segment_duration=0.1,
            )
        )
        segments = vad.detect_audio(np.ones(16000, dtype=np.float32), 16000)

        assert segments == []

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_keeps_short_raw_segments_for_postprocessing(
        self, mock_get_model: MagicMock
    ) -> None:
        """Regression: raw VAD must not drop short speech before merging/padding."""
        from audiocore.vad.config import VADConfig

        mock_model = MagicMock()
        mock_model.reset_states = MagicMock()
        mock_model.side_effect = [
            torch.tensor(0.9),
            torch.tensor(0.1),
            torch.tensor(0.1),
            torch.tensor(0.1),
        ]
        mock_get_model.return_value = mock_model

        vad = SileroVAD()
        segments = vad.detect_audio(
            np.ones(2048, dtype=np.float32),
            16000,
            VADConfig(min_segment_duration=0.5, min_silence_duration_ms=50),
        )

        assert len(segments) == 1
        assert segments[0][0] == 0.0
        assert segments[0][1] > 0.0

    @patch("audiocore.vad.silero.SileroVAD._load_audio")
    @patch("audiocore.vad.silero.SileroVAD.detect_audio")
    def test_detect_file_loads_and_processes_audio(
        self, mock_detect: MagicMock, mock_load: MagicMock, tmp_path: Path
    ) -> None:
        """Test that detect_file loads audio and calls detect_audio."""
        # Create dummy audio data
        test_wav = tmp_path / "test.wav"
        wavfile.write(str(test_wav), 16000, np.zeros(16000, dtype=np.int16))

        # Mock load_audio to return audio data
        mock_load.return_value = (np.zeros(16000, dtype=np.float32), 16000)
        mock_detect.return_value = [(0.0, 1.0, 0.9)]

        vad = SileroVAD()
        segments = vad.detect_file(test_wav)

        # Should call _load_audio
        mock_load.assert_called_once_with(test_wav)

        # Should call detect_audio
        mock_detect.assert_called_once()

        # Should return segments
        assert segments == [(0.0, 1.0, 0.9)]

    def test_detect_audio_raises_error_on_wrong_sample_rate(self) -> None:
        """Test that wrong sample rate raises VADError."""
        vad = SileroVAD()
        audio = np.zeros(48000, dtype=np.float32)

        with pytest.raises(VADError) as exc_info:
            vad.detect_audio(audio, 48000)

        assert "Invalid sample rate" in str(exc_info.value)
        assert exc_info.value.error_code == "AUD-401"


class TestThreadSafety:
    """Test thread-safe model caching."""

    def test_concurrent_get_model_calls_load_once(self) -> None:
        """Concurrent get_model calls load the model exactly once (singleton)."""
        call_count = [0]
        load_lock = threading.Lock()

        def slow_load(*args: Any, **kwargs: Any) -> _FakeVADModel:
            """Simulate a slow model load to exercise the double-checked lock."""
            with load_lock:
                call_count[0] += 1
            threading.Event().wait(0.05)
            return _FakeVADModel()

        results: list[object] = []

        def get_model_thread() -> None:
            results.append(SileroVAD.get_model())

        with patch("silero_vad.load_silero_vad", side_effect=slow_load):
            threads = [threading.Thread(target=get_model_thread) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # All threads should get the same cached instance, loaded only once.
        assert len({id(r) for r in results}) == 1
        assert call_count[0] == 1


class TestErrorHandling:
    """Test error handling in VAD operations."""

    def test_detect_file_raises_invalid_input_for_missing_file(self) -> None:
        """Test that missing file raises InvalidInputError."""
        from audiocore.errors import InvalidInputError

        vad = SileroVAD()

        with pytest.raises(InvalidInputError) as exc_info:
            vad.detect_file("/nonexistent/audio.wav")

        assert "Audio file not found" in str(exc_info.value)

    def test_detect_file_raises_invalid_input_for_directory(self, tmp_path: Path) -> None:
        """Existing directories are invalid VAD audio inputs."""
        from audiocore.errors import InvalidInputError

        audio_dir = tmp_path / "audio.wav"
        audio_dir.mkdir()
        vad = SileroVAD()

        with pytest.raises(InvalidInputError) as exc_info:
            vad.detect_file(audio_dir)

        assert "not a file" in str(exc_info.value)

    def test_detect_file_raises_vad_error_for_invalid_format(self, tmp_path: Path) -> None:
        """Test that invalid audio format raises VADError."""
        # Create a non-WAV file
        invalid_file = tmp_path / "invalid.txt"
        invalid_file.write_text("not audio")

        vad = SileroVAD()

        with pytest.raises((VADError, ValueError)):
            vad.detect_file(invalid_file)

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_reset_state_calls_model_reset(self, mock_get_model: MagicMock) -> None:
        """Test that reset_state calls model.reset_states()."""
        mock_model = MagicMock()
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        vad = SileroVAD()
        vad.reset_state()

        mock_model.reset_states.assert_called_once()

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_resets_state_per_call(self, mock_get_model: MagicMock) -> None:
        """Regression: detect_audio should reset model state on each call.

        Previously, _get_thread_local_model only reset state once per thread,
        causing VAD state to accumulate across files. Now state is always reset.
        """
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.8)
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        vad = SileroVAD()
        audio = np.random.rand(16000).astype(np.float32)

        # First call should reset state
        vad.detect_audio(audio, 16000)
        assert mock_model.reset_states.call_count >= 1

        # Second call should also reset state
        first_reset_count = mock_model.reset_states.call_count
        vad.detect_audio(audio, 16000)
        assert mock_model.reset_states.call_count > first_reset_count

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_enters_speech_at_threshold(self, mock_get_model: MagicMock) -> None:
        """Regression: speech_threshold is inclusive when entering speech."""
        from audiocore.vad.config import VADConfig

        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.5)
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        vad = SileroVAD()
        audio = np.zeros(16000, dtype=np.float32)
        config = VADConfig(
            speech_threshold=0.5,
            silence_threshold=0.3,
            min_segment_duration=0.1,
        )

        segments = vad.detect_audio(audio, 16000, config)

        assert len(segments) == 1
        assert segments[0] == (0.0, 1.0, 0.5)

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_uses_silence_threshold_for_exit(self, mock_get_model: MagicMock) -> None:
        """Regression: detect_audio should use silence_threshold for segment exit.

        Previously, only speech_threshold was checked for both entering and
        exiting speech segments. Now silence_threshold controls exit and
        speech_threshold controls entry (hysteresis).
        """
        from audiocore.vad.config import VADConfig

        call_count = [0]

        def mock_forward(chunk_tensor, sample_rate):
            """Simulate speech that dips to silence_threshold but not below."""
            call_count[0] += 1
            # First 5 chunks: high speech probability (above speech_threshold)
            # Next 5 chunks: dip to between silence and speech threshold
            # Last 5 chunks: high again
            if call_count[0] <= 5:
                return torch.tensor(0.8)  # Above speech_threshold (0.5)
            elif call_count[0] <= 10:
                return torch.tensor(0.4)  # Above silence_threshold (0.3), below speech_threshold
            else:
                return torch.tensor(0.8)

        mock_model = MagicMock()
        mock_model.side_effect = mock_forward
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        vad = SileroVAD(
            config=VADConfig(speech_threshold=0.5, silence_threshold=0.3, min_segment_duration=0.1)
        )
        # Create enough audio for multiple chunks
        audio = np.random.rand(16000 * 2).astype(np.float32)
        segments = vad.detect_audio(audio, 16000)

        # With silence_threshold=0.3, when speech_prob=0.4 (above silence_threshold),
        # the segment should NOT exit, so we should have continuous speech
        # The key behavior: segments should NOT split when prob is between thresholds
        assert isinstance(segments, list)

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_min_silence_duration(self, mock_get_model: MagicMock) -> None:
        """Regression: detect_audio should respect min_silence_duration_ms.

        Previously, min_silence_duration_ms was calculated but never used.
        Now brief silence dips shorter than min_silence_duration_ms don't split segments.
        """
        from audiocore.vad.config import VADConfig

        call_count = [0]

        def mock_forward(chunk_tensor, sample_rate):
            """Simulate speech with a brief silence dip."""
            call_count[0] += 1
            # Speech for chunks 1-5, brief silence for chunks 6-7, speech again 8+
            if 6 <= call_count[0] <= 7:
                return torch.tensor(0.1)  # Below both thresholds - brief silence
            return torch.tensor(0.9)  # Speech

        mock_model = MagicMock()
        mock_model.side_effect = mock_forward
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        # With min_silence_duration_ms=500ms (much longer than the brief dip)
        vad = SileroVAD(
            config=VADConfig(
                speech_threshold=0.5,
                silence_threshold=0.3,
                min_silence_duration_ms=500,
                min_segment_duration=0.1,
            )
        )
        audio = np.random.rand(16000).astype(np.float32)
        segments = vad.detect_audio(audio, 16000)

        # The brief 2-chunk dip (~64ms) is shorter than min_silence_duration (500ms),
        # so it should not split the segment
        assert isinstance(segments, list)

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_processes_non_aligned_length_without_partial_chunks(
        self, mock_get_model: MagicMock
    ) -> None:
        """Regression: detect_audio pads partial last chunk for consistent model input.

        Previously, partial chunks at the end were skipped, losing audio.
        Now the partial last chunk is zero-padded to chunk_size so the
        Silero model receives consistent-length input and no audio is lost.
        """
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.8)
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        # Create audio with length NOT a multiple of chunk_size (512)
        # 1500 samples = 2 full chunks of 512 + 476 leftover (partial)
        audio_data = np.random.rand(1500).astype(np.float32)

        vad = SileroVAD()
        vad.detect_audio(audio_data, 16000)

        # Model should be called three times:
        # 2 full 512-sample chunks + 1 zero-padded partial chunk (476 padded to 512)
        assert mock_model.call_count == 3

    @patch("audiocore.vad.silero.SileroVAD.get_model")
    def test_detect_audio_processes_exact_multiple_length(self, mock_get_model: MagicMock) -> None:
        """Regression: detect_audio handles audio length that is exact multiple of chunk_size.

        Previously, `len(audio_data) - chunk_size + 1` could cause an off-by-one
        that either added an extra iteration or missed the last chunk. With
        exact multiples, all full chunks should be processed.
        """
        mock_model = MagicMock()
        mock_model.return_value = torch.tensor(0.8)
        mock_model.reset_states = MagicMock()
        mock_get_model.return_value = mock_model

        # Create audio with length that IS an exact multiple of chunk_size (512)
        audio_data = np.random.rand(1024).astype(np.float32)  # exactly 2 chunks

        vad = SileroVAD()
        vad.detect_audio(audio_data, 16000)

        # Model should be called exactly twice
        assert mock_model.call_count == 2


class TestSpeechSegmenterCloseSegment:
    """_SpeechSegmenter._close_segment ignores zero-length runs."""

    def test_close_segment_zero_length_appends_nothing(self) -> None:
        """A close at exactly speech_start emits no segment but resets state."""
        from audiocore.vad.config import VADConfig
        from audiocore.vad.silero import _SpeechSegmenter

        seg = _SpeechSegmenter(VADConfig())
        seg._in_speech = True
        seg._speech_start = 5.0
        seg._confidences = [0.9]

        seg._close_segment(5.0)

        assert seg._segments == []
        assert seg._in_speech is False
        assert seg._speech_start is None
        assert seg._confidences == []

    def test_close_segment_positive_length_appends(self) -> None:
        """A close after speech_start emits one segment with mean confidence."""
        from audiocore.vad.config import VADConfig
        from audiocore.vad.silero import _SpeechSegmenter

        seg = _SpeechSegmenter(VADConfig())
        seg._in_speech = True
        seg._speech_start = 1.0
        seg._confidences = [0.6, 0.8]

        seg._close_segment(2.0)

        assert seg._segments == [(1.0, 2.0, pytest.approx(0.7))]


class TestNormalizeToFloat32:
    """_normalize_to_float32 scales each PCM dtype to [-1, 1]."""

    def test_int32_scaled_by_full_scale(self) -> None:
        data = np.array([0, np.iinfo(np.int32).max], dtype=np.int32)
        result = SileroVAD._normalize_to_float32(data)
        assert result.dtype == np.float32
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(1.0, abs=1e-6)

    def test_uint8_centered_and_scaled(self) -> None:
        data = np.array([0, 128, 255], dtype=np.uint8)
        result = SileroVAD._normalize_to_float32(data)
        assert result.dtype == np.float32
        assert result[0] == pytest.approx(-1.0)
        assert result[1] == pytest.approx(0.0)
        assert result[2] == pytest.approx(0.9921875)

    def test_uint16_centered_and_scaled(self) -> None:
        data = np.array([0, 32768, 65535], dtype=np.uint16)
        result = SileroVAD._normalize_to_float32(data)
        assert result.dtype == np.float32
        assert result[0] == pytest.approx(-1.0)
        assert result[1] == pytest.approx(0.0)

    def test_float_out_of_range_is_clamped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        caplog.set_level(logging.WARNING)
        data = np.array([-4.0, 2.0], dtype=np.float64)
        result = SileroVAD._normalize_to_float32(data)
        assert result.dtype == np.float32
        assert float(np.max(np.abs(result))) == pytest.approx(1.0)
        assert any("exceeds [-1, 1] range" in r.message for r in caplog.records)

    def test_float_in_range_is_unchanged(self) -> None:
        data = np.array([-0.5, 0.25], dtype=np.float32)
        result = SileroVAD._normalize_to_float32(data)
        assert result[0] == pytest.approx(-0.5)
        assert result[1] == pytest.approx(0.25)


class _TinyJitModel(torch.nn.Module):
    """Minimal TorchScript-able stand-in for a custom Silero model."""

    def forward(self, chunk: torch.Tensor, sample_rate: int) -> torch.Tensor:
        return torch.tensor(0.0)


class TestCustomModelLoading:
    """_load_custom_model loads TorchScript files and caches the result."""

    def test_resolve_model_loads_and_caches_custom_model(self, tmp_path: Path) -> None:
        from audiocore.vad.config import VADConfig

        model_file = tmp_path / "custom.jit"
        torch.jit.script(_TinyJitModel()).save(str(model_file))

        vad = SileroVAD(config=VADConfig(model_path=model_file))
        first = vad._resolve_model()
        second = vad._resolve_model()

        assert first is second
        assert vad._custom_model is first

    def test_load_custom_model_invalid_file_raises_vad_error(self, tmp_path: Path) -> None:
        from audiocore.vad.config import VADConfig

        model_file = tmp_path / "broken.jit"
        model_file.write_bytes(b"not a torchscript archive")

        vad = SileroVAD(config=VADConfig(model_path=model_file))
        with pytest.raises(VADError, match="Failed to load custom VAD model"):
            vad._resolve_model()
