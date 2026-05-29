"""Tests for diarization wiring into the pipeline and the pyannote backend."""

from __future__ import annotations

from pathlib import Path

import pytest

from audiocore.diarization import PyannoteDiarizer, SpeakerTurn
from audiocore.errors import ProcessingError
from audiocore.models import (
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
)
from audiocore.pipeline import Pipeline
from audiocore.pipeline.progress import PipelineStage
from audiocore.types import BackendType


class _FixedDiarizer:
    """Diarizer returning one turn covering an early window."""

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def diarize(self, audio_path: Path | str) -> list[SpeakerTurn]:
        self.calls.append(Path(audio_path))
        return [SpeakerTurn(0.0, 5.0, "SPEAKER_00")]


def _result_with_segment() -> TranscriptionResult:
    return TranscriptionResult(
        segments=[Segment(start_time=0.0, end_time=4.0, text="hello")],
        media_info=MediaInfo(duration=4.0, format="wav"),
        config_used=TranscriptionOptions(),
        processing_time_seconds=0.0,
        backend_used=BackendType.FASTER_WHISPER,
    )


class TestDiarizeStage:
    """Pipeline._diarize_stage labels segments only when a diarizer is set."""

    def test_diarize_stage_labels_segments(self, tmp_path: Path) -> None:
        """With a diarizer, segments are labeled and the audio path is used."""
        diarizer = _FixedDiarizer()
        pipeline = Pipeline(diarizer=diarizer)
        result = _result_with_segment()
        audio = tmp_path / "clip.wav"

        emitted: list[PipelineStage] = []
        pipeline._diarize_stage(result, audio, lambda stage, p, m: emitted.append(stage))

        assert result.segments[0].speaker == "SPEAKER_00"
        assert diarizer.calls == [audio]
        assert PipelineStage.DIARIZING in emitted

    def test_diarize_stage_noop_without_diarizer(self, tmp_path: Path) -> None:
        """Without a diarizer, segments are untouched and no stage is emitted."""
        pipeline = Pipeline()
        result = _result_with_segment()

        emitted: list[PipelineStage] = []
        pipeline._diarize_stage(
            result, tmp_path / "clip.wav", lambda stage, p, m: emitted.append(stage)
        )

        assert result.segments[0].speaker is None
        assert emitted == []


class TestPyannoteDiarizerErrors:
    """PyannoteDiarizer raises typed errors when prerequisites are missing."""

    def test_missing_pyannote_raises_processing_error(self) -> None:
        """Without pyannote.audio installed, diarize raises ProcessingError."""
        diarizer = PyannoteDiarizer(auth_token="hf_dummy")
        with pytest.raises(ProcessingError, match="pyannote.audio"):
            diarizer.diarize("clip.wav")
