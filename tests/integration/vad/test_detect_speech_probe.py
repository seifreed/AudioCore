"""Integration tests for ``detect_speech`` duration auto-detection.

When ``total_duration`` is omitted, ``detect_speech`` probes the file with
ffprobe. These exercise the real probe boundary: a valid WAV resolves its
duration, and an unreadable file surfaces ``MediaError`` translated into a
typed ``VADError``.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Any

import pytest

from audiocore.errors import VADError
from audiocore.vad import VADConfig, detect_speech
from audiocore.vad.silero import SileroVAD


def _ffprobe_available() -> bool:
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


requires_ffprobe = pytest.mark.skipif(not _ffprobe_available(), reason="ffprobe not available")


class _FakeVAD:
    """Detector that ignores file content and returns fixed spans."""

    def __init__(self, spans: list[tuple[float, float, float]]) -> None:
        self._spans = spans

    def detect_file(
        self, audio_path: Path | str, config: VADConfig | None = None
    ) -> list[tuple[float, float, float]]:
        return self._spans


def _write_silent_wav(path: Path, *, seconds: float = 2.0, rate: int = 16000) -> None:
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)


@pytest.fixture(autouse=True)
def _reset_silero_singleton() -> Any:
    SileroVAD._model = None
    yield
    SileroVAD._model = None


@requires_ffprobe
class TestDetectSpeechAutoDuration:
    """detect_speech probes the file when total_duration is None."""

    def test_probes_real_wav_for_duration(self, tmp_path: Path) -> None:
        audio = tmp_path / "clip.wav"
        _write_silent_wav(audio, seconds=2.0)
        fake = _FakeVAD([(0.0, 1.0, 0.9)])

        segments = detect_speech(audio, config=VADConfig(), vad=fake)

        assert len(segments) == 1
        assert segments[0].end_time <= 2.0

    def test_unreadable_file_raises_vaderror(self, tmp_path: Path) -> None:
        garbage = tmp_path / "broken.wav"
        garbage.write_bytes(b"not a real wav payload")
        fake = _FakeVAD([(0.0, 0.5, 0.9)])

        with pytest.raises(VADError) as exc_info:
            detect_speech(garbage, config=VADConfig(), vad=fake)

        assert exc_info.value.context["path"] == str(garbage)
