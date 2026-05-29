"""Regression tests for custom VAD models (v2.0 roadmap).

Covers the two extension points:
- A fully custom detector implementing the ``VADModel`` protocol can be passed
  to ``detect_speech`` and its raw spans flow through segment post-processing.
- ``VADConfig.model_path`` selects a custom Silero-format model file, and a
  missing path raises a typed ``VADError`` (no torch model load required).
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

from audiocore.errors import VADError
from audiocore.vad import VADConfig, VADModel, detect_speech
from audiocore.vad.silero import SileroVAD


class _FakeVAD:
    """A minimal detector returning fixed raw speech spans."""

    def __init__(self, spans: list[tuple[float, float, float]]) -> None:
        self._spans = spans
        self.calls: list[Path] = []

    def detect_file(
        self,
        audio_path: Path | str,
        config: VADConfig | None = None,
    ) -> list[tuple[float, float, float]]:
        self.calls.append(Path(audio_path))
        return self._spans


def _write_silent_wav(path: Path, *, seconds: float = 5.0, rate: int = 16000) -> None:
    """Write a mono 16kHz silent WAV so detect_speech has a real file to open."""
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)


class TestCustomVADModelProtocol:
    """A custom detector is accepted and drives the speech-detection stage."""

    def test_fake_vad_satisfies_protocol(self) -> None:
        """The fake detector is recognized as a VADModel structurally."""
        assert isinstance(_FakeVAD([]), VADModel)

    def test_detect_speech_uses_custom_vad(self, tmp_path: Path) -> None:
        """detect_speech routes through the supplied detector, not Silero."""
        audio = tmp_path / "clip.wav"
        _write_silent_wav(audio, seconds=5.0)
        fake = _FakeVAD([(0.0, 2.0, 0.9), (3.0, 4.5, 0.8)])

        segments = detect_speech(audio, config=VADConfig(), total_duration=5.0, vad=fake)

        assert fake.calls == [audio]
        assert len(segments) == 2
        assert segments[0].start_time >= 0.0
        assert segments[1].end_time <= 5.0

    def test_detect_speech_custom_vad_empty(self, tmp_path: Path) -> None:
        """An empty detection yields no segments without touching Silero."""
        audio = tmp_path / "clip.wav"
        _write_silent_wav(audio, seconds=2.0)
        fake = _FakeVAD([])

        segments = detect_speech(audio, config=VADConfig(), total_duration=2.0, vad=fake)

        assert segments == []


class TestSileroCustomModelPath:
    """VADConfig.model_path selects a custom Silero-format model file."""

    def test_config_model_path_default_none(self) -> None:
        """model_path defaults to None (use bundled weights)."""
        assert VADConfig().model_path is None

    def test_config_accepts_model_path(self, tmp_path: Path) -> None:
        """model_path is coerced to a Path."""
        config = VADConfig(model_path=str(tmp_path / "custom.jit"))
        assert config.model_path == tmp_path / "custom.jit"

    def test_silero_propagates_config_model_path(self, tmp_path: Path) -> None:
        """SileroVAD picks up model_path from its config."""
        custom = tmp_path / "custom.jit"
        vad = SileroVAD(config=VADConfig(model_path=custom))
        assert vad._custom_model_path == custom

    def test_missing_custom_model_raises_vaderror(self, tmp_path: Path) -> None:
        """Resolving a non-existent custom model file raises a typed VADError."""
        vad = SileroVAD(config=VADConfig(model_path=tmp_path / "nope.jit"))
        with pytest.raises(VADError, match="Custom VAD model not found"):
            vad._resolve_model()
