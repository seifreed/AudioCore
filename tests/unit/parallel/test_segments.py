"""Unit tests for segment-level parallel processing.

Contract change: ``transcribe_segments_parallel()`` was previously a placeholder
that raised ``NotImplementedError``. It now extracts each segment's audio range,
transcribes it on the selected backend, and merges the per-segment results back
into the original timeline. These tests pin the new behavior:

- segments are transcribed and their timings offset into the source timeline
- results are returned in chronological order
- zero-duration segments are skipped
- empty input yields an empty result (no backend work)
- argument validation (max_workers, missing file) still happens up front

Backends are wired through the real ``BackendRegistry`` seam using an in-memory
``TranscriptionBackend``; only the ffmpeg subprocess boundary (``extract_audio``)
is stubbed, per the project's no-mocks-for-internal-collaboration rule.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from audiocore.backends import BackendRegistry, register_builtin_backends
from audiocore.backends.base import TranscriptionBackend
from audiocore.errors import InvalidInputError
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.parallel.segments import transcribe_segments_parallel
from audiocore.types import BackendType


class _RecordingBackend(TranscriptionBackend):
    """In-memory backend that records the clips it transcribes.

    Returns a single segment spanning [0.0, 0.4] for every clip so callers can
    assert that the per-clip timings are offset by each source segment's start.

    Clips are recorded at class level so a test can observe the work regardless
    of which cached instance the registry hands to the function under test.
    """

    transcribed_clips: list[Path] = []

    def __init__(self, config: object | None = None) -> None:
        self._config = config

    @property
    def backend_type(self) -> BackendType:
        return BackendType.OPENAI

    def transcribe(
        self, audio_path: Path | str, options: TranscriptionOptions
    ) -> TranscriptionResult:
        type(self).transcribed_clips.append(Path(audio_path))
        return TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=0.4, text="clip text", confidence=0.9)],
            media_info=MediaInfo(duration=0.5, format="wav"),
            config_used=options,
            processing_time_seconds=0.01,
            backend_used=BackendType.OPENAI,
        )

    def get_name(self) -> str:
        return "Recording Backend"

    def is_available(self) -> bool:
        return True

    def get_model_options(self) -> list[str]:
        return ["recording"]


def _stub_extract_audio(input_path: Any, output_path: Any = None, **kwargs: Any) -> Path:
    """Stand in for the ffmpeg-backed extractor: create a non-empty clip file."""
    clip = Path(output_path)
    clip.write_bytes(b"clip-audio")
    return clip


@pytest.fixture
def openai_backend(monkeypatch: pytest.MonkeyPatch) -> _RecordingBackend:
    """Register an in-memory OpenAI backend through the real registry seam."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    _RecordingBackend.transcribed_clips = []
    registry = BackendRegistry()
    registry._reset()
    register_builtin_backends()
    registry.register(BackendType.OPENAI, _RecordingBackend)
    yield registry.get_backend(BackendType.OPENAI)
    registry._reset()
    _RecordingBackend.transcribed_clips = []


def _openai_options() -> TranscriptionOptions:
    return TranscriptionOptions(backend=BackendType.OPENAI)


class TestTranscribeSegmentsParallel:
    """Tests for the implemented transcribe_segments_parallel function."""

    def test_offsets_segments_into_source_timeline(
        self, tmp_path: Path, openai_backend: _RecordingBackend
    ) -> None:
        """Each clip's segment timings are shifted by the source segment's start."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"source-audio")
        segments = [
            Segment(start_time=0.0, end_time=5.0, text=""),
            Segment(start_time=10.0, end_time=15.0, text=""),
        ]
        media_info = MediaInfo(duration=20.0, format="wav")

        with patch("audiocore.parallel.segments.extract_audio", side_effect=_stub_extract_audio):
            result = transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=_openai_options(),
                media_info=media_info,
            )

        starts = [segment.start_time for segment in result.segments]
        assert starts == [0.0, 10.0]

    def test_returns_segments_in_chronological_order(
        self, tmp_path: Path, openai_backend: _RecordingBackend
    ) -> None:
        """Merged output is sorted by start time regardless of input order."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"source-audio")
        segments = [
            Segment(start_time=10.0, end_time=15.0, text=""),
            Segment(start_time=0.0, end_time=5.0, text=""),
            Segment(start_time=5.0, end_time=10.0, text=""),
        ]
        media_info = MediaInfo(duration=20.0, format="wav")

        with patch("audiocore.parallel.segments.extract_audio", side_effect=_stub_extract_audio):
            result = transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=_openai_options(),
                media_info=media_info,
            )

        starts = [segment.start_time for segment in result.segments]
        assert starts == sorted(starts)
        assert starts == [0.0, 5.0, 10.0]

    def test_reports_backend_used(self, tmp_path: Path, openai_backend: _RecordingBackend) -> None:
        """The result records the backend that performed transcription."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"source-audio")
        segments = [Segment(start_time=0.0, end_time=5.0, text="")]
        media_info = MediaInfo(duration=10.0, format="wav")

        with patch("audiocore.parallel.segments.extract_audio", side_effect=_stub_extract_audio):
            result = transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=_openai_options(),
                media_info=media_info,
            )

        assert result.backend_used == BackendType.OPENAI

    def test_skips_zero_duration_segments(
        self, tmp_path: Path, openai_backend: _RecordingBackend
    ) -> None:
        """Segments with no duration are not extracted or transcribed."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"source-audio")
        segments = [
            Segment(start_time=3.0, end_time=3.0, text=""),  # zero-length: skipped
            Segment(start_time=5.0, end_time=9.0, text=""),
        ]
        media_info = MediaInfo(duration=10.0, format="wav")

        with patch("audiocore.parallel.segments.extract_audio", side_effect=_stub_extract_audio):
            result = transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=_openai_options(),
                media_info=media_info,
            )

        assert len(openai_backend.transcribed_clips) == 1
        assert [segment.start_time for segment in result.segments] == [5.0]

    def test_empty_segments_returns_empty_result_without_backend_work(
        self, tmp_path: Path, openai_backend: _RecordingBackend
    ) -> None:
        """No segments means an empty result and no extraction/transcription."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"source-audio")
        media_info = MediaInfo(duration=10.0, format="wav")

        with patch("audiocore.parallel.segments.extract_audio", side_effect=_stub_extract_audio):
            result = transcribe_segments_parallel(
                segments=[],
                audio_path=audio_path,
                options=_openai_options(),
                media_info=media_info,
            )

        assert result.segments == []
        assert openai_backend.transcribed_clips == []

    def test_raises_value_error_for_invalid_max_workers(
        self, tmp_path: Path, openai_backend: _RecordingBackend
    ) -> None:
        """max_workers below 1 is rejected before any work begins."""
        audio_path = tmp_path / "audio.wav"
        audio_path.write_bytes(b"source-audio")

        with pytest.raises(ValueError, match="max_workers"):
            transcribe_segments_parallel(
                segments=[Segment(start_time=0.0, end_time=5.0, text="")],
                audio_path=audio_path,
                options=_openai_options(),
                max_workers=0,
            )

    def test_raises_invalid_input_for_missing_audio_file(
        self, tmp_path: Path, openai_backend: _RecordingBackend
    ) -> None:
        """A missing source file raises InvalidInputError before backend work."""
        missing = tmp_path / "does_not_exist.wav"

        with pytest.raises(InvalidInputError):
            transcribe_segments_parallel(
                segments=[Segment(start_time=0.0, end_time=5.0, text="")],
                audio_path=missing,
                options=_openai_options(),
            )
