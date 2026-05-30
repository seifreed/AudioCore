"""Unit tests for the pyannote-backed speaker diarizer.

pyannote.audio is an optional, gated dependency that is not installed in the
test environment, so a fake ``pyannote.audio`` module (the external boundary)
is injected to drive the pipeline loading, execution, and conversion paths.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from audiocore.diarization.pyannote_diarizer import (
    PyannoteDiarizer,
    _annotation_to_turns,
)
from audiocore.errors import ProcessingError


class _FakeAnnotation:
    """Minimal stand-in for a pyannote Annotation."""

    def __init__(self, tracks):
        self._tracks = tracks

    def itertracks(self, yield_label=False):
        for start, end, speaker in self._tracks:
            yield SimpleNamespace(start=start, end=end), "track", speaker


def _install_fake_pyannote(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pipeline_call=None,
    from_pretrained_raises: bool = False,
):
    captured: dict[str, object] = {}

    def _pipeline(audio_path, **kwargs):
        captured["audio_path"] = audio_path
        captured["kwargs"] = kwargs
        if pipeline_call is not None:
            return pipeline_call(audio_path, **kwargs)
        return _FakeAnnotation([(0.0, 1.0, "SPEAKER_00")])

    class _Pipeline:
        @staticmethod
        def from_pretrained(model, use_auth_token=None):
            captured["model"] = model
            captured["token"] = use_auth_token
            if from_pretrained_raises:
                raise RuntimeError("model load blew up")
            return _pipeline

    pyannote_pkg = types.ModuleType("pyannote")
    audio_mod = types.ModuleType("pyannote.audio")
    audio_mod.Pipeline = _Pipeline
    pyannote_pkg.audio = audio_mod
    monkeypatch.setitem(sys.modules, "pyannote", pyannote_pkg)
    monkeypatch.setitem(sys.modules, "pyannote.audio", audio_mod)
    return captured


class TestAnnotationToTurns:
    """_annotation_to_turns converts pyannote tracks into SpeakerTurns."""

    def test_converts_tracks(self) -> None:
        annotation = _FakeAnnotation([(0.0, 1.5, "SPEAKER_00"), (1.5, 2.0, "SPEAKER_01")])
        turns = _annotation_to_turns(annotation)
        assert len(turns) == 2
        assert turns[0].start_time == 0.0
        assert turns[0].end_time == 1.5
        assert turns[0].speaker == "SPEAKER_00"
        assert turns[1].speaker == "SPEAKER_01"


class TestResolveToken:
    """_resolve_token reads the constructor value then the environment."""

    def test_constructor_token_is_stripped(self) -> None:
        diarizer = PyannoteDiarizer(auth_token="  hf_abc  ")
        assert diarizer._resolve_token() == "hf_abc"

    def test_env_token_used_when_constructor_blank(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        monkeypatch.setenv("HF_TOKEN", "hf_env")
        diarizer = PyannoteDiarizer()
        assert diarizer._resolve_token() == "hf_env"

    def test_returns_none_when_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        monkeypatch.delenv("HF_TOKEN", raising=False)
        diarizer = PyannoteDiarizer()
        assert diarizer._resolve_token() is None


class TestGetPipeline:
    """_get_pipeline validates prerequisites and caches the loaded pipeline."""

    def test_missing_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_pyannote(monkeypatch)
        monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
        monkeypatch.delenv("HF_TOKEN", raising=False)
        diarizer = PyannoteDiarizer()
        with pytest.raises(ProcessingError, match="Hugging Face access token"):
            diarizer._get_pipeline()

    def test_from_pretrained_failure_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_pyannote(monkeypatch, from_pretrained_raises=True)
        diarizer = PyannoteDiarizer(auth_token="hf_abc")
        with pytest.raises(ProcessingError, match="Failed to load diarization model"):
            diarizer._get_pipeline()

    def test_caches_loaded_pipeline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_pyannote(monkeypatch)
        diarizer = PyannoteDiarizer(auth_token="hf_abc")
        first = diarizer._get_pipeline()
        second = diarizer._get_pipeline()
        assert first is second


class TestDiarize:
    """diarize loads the pipeline, runs it, and converts the annotation."""

    def test_returns_speaker_turns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _install_fake_pyannote(monkeypatch)
        diarizer = PyannoteDiarizer(auth_token="hf_abc")
        turns = diarizer.diarize("meeting.wav")
        assert len(turns) == 1
        assert turns[0].speaker == "SPEAKER_00"

    def test_passes_num_speakers_to_pipeline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _install_fake_pyannote(monkeypatch)
        diarizer = PyannoteDiarizer(auth_token="hf_abc", num_speakers=3)
        diarizer.diarize("meeting.wav")
        assert captured["kwargs"] == {"num_speakers": 3}

    def test_pipeline_failure_raises_processing_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(audio_path, **kwargs):
            raise RuntimeError("inference exploded")

        _install_fake_pyannote(monkeypatch, pipeline_call=_boom)
        diarizer = PyannoteDiarizer(auth_token="hf_abc")
        with pytest.raises(ProcessingError, match="Speaker diarization failed"):
            diarizer.diarize("meeting.wav")
