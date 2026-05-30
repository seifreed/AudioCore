"""Unit tests for the ``audiocore.vad.detect_speech`` entry point and the
package-level lazy ``SileroVAD`` import.

These cover the paths that do not shell out to ffprobe: the lazy attribute
hook, the missing-file guard, and the default-detector branch (Silero model
loading is patched at its true external boundary, ``load_silero_vad``).
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import torch

import audiocore.vad as vad_pkg
from audiocore.errors import InvalidInputError
from audiocore.vad import VADConfig, detect_speech
from audiocore.vad.silero import SileroVAD


class _FakeVADModel:
    """In-memory stand-in for the Silero JIT model (never speech)."""

    def reset_states(self) -> None:
        return None

    def __call__(self, chunk: object, sample_rate: int) -> torch.Tensor:
        return torch.tensor(0.0)


@pytest.fixture(autouse=True)
def _reset_silero_singleton() -> Any:
    SileroVAD._model = None
    yield
    SileroVAD._model = None


def _write_silent_wav(path: Path, *, seconds: float = 1.0, rate: int = 16000) -> None:
    frames = int(seconds * rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)


class TestLazySileroAttribute:
    """The package exposes SileroVAD lazily via module __getattr__."""

    def test_getattr_silero_returns_class(self) -> None:
        assert vad_pkg.SileroVAD is SileroVAD

    def test_getattr_unknown_name_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError, match="has no attribute 'nope'"):
            vad_pkg.__getattr__("nope")


class TestDetectSpeechGuards:
    """detect_speech validates inputs before doing any work."""

    def test_missing_file_raises_invalid_input(self, tmp_path: Path) -> None:
        missing = tmp_path / "absent.wav"
        with pytest.raises(InvalidInputError) as exc_info:
            detect_speech(missing, total_duration=1.0)
        assert exc_info.value.context["path"] == str(missing)


class TestDetectSpeechDefaultDetector:
    """With no detector supplied, detect_speech builds a SileroVAD."""

    def test_default_detector_runs_silero_on_silent_clip(self, tmp_path: Path) -> None:
        audio = tmp_path / "silent.wav"
        _write_silent_wav(audio, seconds=1.0)

        with patch("silero_vad.load_silero_vad", return_value=_FakeVADModel()):
            segments = detect_speech(audio, config=VADConfig(), total_duration=1.0)

        assert segments == []
