"""Integration tests for Faster-Whisper backend.

These tests require faster-whisper package and may download models
on first run. Tests are skipped if:
- faster-whisper not installed
- Integration test flag not set
- No models available

Run with: pytest tests/integration/backends/test_faster_whisper_integration.py -m integration
"""

from __future__ import annotations

import struct
import time
import wave
from pathlib import Path

import pytest

from audiocore.backends import BackendRegistry, FasterWhisperBackend
from audiocore.backends.faster_whisper import ModelManager, get_best_device
from audiocore.config.faster_whisper_config import FasterWhisperConfig
from audiocore.models import TranscriptionOptions
from audiocore.types import BackendType, ModelSize


def _has_faster_whisper() -> bool:
    """Check if faster-whisper is installed."""
    try:
        import faster_whisper  # noqa: F401

        return True
    except ImportError:
        return False


def _create_silent_wav(path: Path, duration: float = 1.0) -> None:
    """Create a silent WAV file.

    Args:
        path: Path to save WAV file
        duration: Duration in seconds (default 1.0)
    """
    samples = int(16000 * duration)

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz

        silence = struct.pack("<" + "H" * samples, *([0] * samples))
        wav_file.writeframes(silence)


# Skip all tests in this module if faster-whisper not installed
pytestmark = pytest.mark.skipif(
    not _has_faster_whisper(),
    reason="faster-whisper not installed - skipping integration tests",
)


@pytest.fixture
def test_audio(tmp_path: Path) -> Path:
    """Create a 1-second silent WAV file for testing.

    Uses Python wave module to create valid WAV format.
    """
    audio_path = tmp_path / "test_audio.wav"
    _create_silent_wav(audio_path, duration=1.0)
    return audio_path


@pytest.fixture
def faster_whisper_config() -> FasterWhisperConfig:
    """Create test configuration with tiny model for speed."""
    return FasterWhisperConfig(
        model_size=ModelSize.TINY,
        device=None,  # Auto-detect
        compute_type="int8",  # Faster on CPU
        beam_size=1,  # Faster for testing
    )


@pytest.mark.integration
class TestFasterWhisperIntegration:
    """Integration tests with real faster-whisper execution."""

    def test_backend_registration(self) -> None:
        """Test FasterWhisperBackend is registered."""
        registry = BackendRegistry()

        # Clear and register
        registry.clear()
        registry.register(BackendType.FASTER_WHISPER, FasterWhisperBackend)

        backends = registry.list_backends()
        assert BackendType.FASTER_WHISPER in backends

    def test_backend_availability_check(self) -> None:
        """Test is_available check works."""
        backend = FasterWhisperBackend()

        # Should return True if faster-whisper installed
        if _has_faster_whisper():
            assert backend.is_available() is True
        else:
            assert backend.is_available() is False

    def test_transcribe_silent_audio(
        self, test_audio: Path, faster_whisper_config: FasterWhisperConfig
    ) -> None:
        """Test transcription of silent audio file."""
        backend = FasterWhisperBackend(config=faster_whisper_config)

        # Skip if model not available (integration test without download)
        if not ModelManager().is_model_downloaded("tiny"):
            pytest.skip("Tiny model not cached - would require download")

        options = TranscriptionOptions(model_size=ModelSize.TINY)
        result = backend.transcribe(test_audio, options)

        # Verify result structure
        assert result.backend_used == BackendType.FASTER_WHISPER
        assert result.media_info is not None
        assert result.media_info.duration > 0
        assert isinstance(result.segments, list)

    def test_model_auto_download_on_first_use(
        self, tmp_path: Path, faster_whisper_config: FasterWhisperConfig
    ) -> None:
        """Test that model auto-downloads if not cached."""
        # This test may be slow on first run (downloads model)
        # Use tiny model and small audio for speed

        backend = FasterWhisperBackend(config=faster_whisper_config)

        # Create minimal audio
        audio_path = tmp_path / "test.wav"
        _create_silent_wav(audio_path, duration=0.5)  # 0.5 second

        if not ModelManager().is_model_downloaded("tiny"):
            # Model will download on first transcribe
            start_time = time.time()
            result = backend.transcribe(audio_path, TranscriptionOptions())
            download_time = time.time() - start_time

            # Second transcription should be faster (model cached)
            start_time = time.time()
            result2 = backend.transcribe(audio_path, TranscriptionOptions())
            cached_time = time.time() - start_time

            # Cached should be much faster than download
            # (This is a heuristic, might not hold on slow networks)
            # Just verify both work
            assert result is not None
            assert result2 is not None

        # Verify model now cached
        assert ModelManager().is_model_downloaded("tiny")

    def test_device_selection(self) -> None:
        """Test device detection and selection."""
        device = get_best_device()

        # Should return cuda, mps, or cpu
        assert device in ["cuda", "mps", "cpu"]

        # Backend should use this device
        config = FasterWhisperConfig(device=None)  # Auto
        backend = FasterWhisperBackend(config=config)

        # Verify it works
        assert backend.is_available()


@pytest.mark.integration
class TestModelManagerIntegration:
    """Integration tests for ModelManager."""

    def test_list_models(self) -> None:
        """Test listing available models."""
        manager = ModelManager()

        models = manager.list_models()

        # Should have at least tiny, base, small, medium, large
        model_names = [m.name for m in models]
        assert "tiny" in model_names
        assert "base" in model_names
        assert "small" in model_names
        assert "medium" in model_names
        assert "large" in model_names

    def test_get_model_path(self) -> None:
        """Test getting model path."""
        manager = ModelManager()

        # If model downloaded, should return path
        if manager.is_model_downloaded("tiny"):
            path = manager.get_model_path("tiny")
            assert path is not None
            assert path.exists()


@pytest.mark.integration
class TestBackendRegistryIntegration:
    """Test backend registration with BackendRegistry."""

    def test_register_builtin_backends(self) -> None:
        """Test that register_builtin_backends() registers all backends."""
        from audiocore.backends import register_builtin_backends

        registry = BackendRegistry()
        registry.clear()

        register_builtin_backends()

        backends = registry.list_backends()
        assert BackendType.OPENAI in backends

        # FasterWhisperBackend may not be installed
        if _has_faster_whisper():
            assert BackendType.FASTER_WHISPER in backends

    def test_backend_name(self) -> None:
        """Test backend name retrieval."""
        backend = FasterWhisperBackend()
        name = backend.get_name()

        assert "Faster-Whisper" in name or "faster-whisper" in name.lower()

    def test_backend_model_options(self) -> None:
        """Test backend model options."""
        backend = FasterWhisperBackend()
        options = backend.get_model_options()

        # Should include tiny, base, small, medium, large
        assert "tiny" in options
        assert "base" in options
        assert "small" in options
        assert "medium" in options
        assert "large" in options
