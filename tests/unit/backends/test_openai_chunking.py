"""Unit tests for OpenAI audio chunking helpers.

These helpers shell out to ffmpeg/ffprobe (the external boundary), so the
subprocess and the module-level ffmpeg/ffprobe helpers are mocked to drive
the chunk-splitting orchestration and its error paths deterministically.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiocore.backends import openai_chunking as oc
from audiocore.errors import TranscriptionError


def _make_audio(tmp_path: Path, size: int = 1024) -> Path:
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"\x00" * size)
    return audio


class TestEstimateChunkDuration:
    """estimate_chunk_duration derives duration from observed bitrate."""

    def test_uses_bitrate_estimate_above_minimum(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path, size=1000)
        # duration 10s, target half the file -> ~5s, above the 1s floor.
        result = oc.estimate_chunk_duration(
            audio, 10.0, chunk_target_bytes=500, chunk_min_duration_seconds=1.0
        )
        assert result == pytest.approx(5.0)

    def test_floors_at_minimum(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path, size=1000)
        result = oc.estimate_chunk_duration(
            audio, 1.0, chunk_target_bytes=10, chunk_min_duration_seconds=30.0
        )
        assert result == 30.0


class TestGetAudioDuration:
    """get_audio_duration parses ffprobe output and maps failures."""

    def test_parses_positive_duration(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        completed = MagicMock(stdout="12.5\n")
        with patch("subprocess.run", return_value=completed):
            assert oc.get_audio_duration(audio, ffprobe_path="ffprobe") == pytest.approx(12.5)

    def test_non_positive_duration_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        completed = MagicMock(stdout="0\n")
        with patch("subprocess.run", return_value=completed):
            with pytest.raises(TranscriptionError, match="Failed to read audio duration"):
                oc.get_audio_duration(audio, ffprobe_path="ffprobe")

    def test_missing_ffprobe_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        with patch("subprocess.run", side_effect=FileNotFoundError("no ffprobe")):
            with pytest.raises(TranscriptionError):
                oc.get_audio_duration(audio, ffprobe_path="/bad/ffprobe")


class TestRunFfmpegSegment:
    """run_ffmpeg_segment invokes ffmpeg and maps its failures."""

    def test_success_invokes_subprocess(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        out_dir = tmp_path / "chunks"
        out_dir.mkdir()
        with patch("subprocess.run") as run:
            oc.run_ffmpeg_segment(audio, out_dir, 30.0, ffmpeg_path="ffmpeg")
        run.assert_called_once()

    def test_missing_ffmpeg_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        out_dir = tmp_path / "chunks"
        out_dir.mkdir()
        with patch("subprocess.run", side_effect=FileNotFoundError("no ffmpeg")):
            with pytest.raises(TranscriptionError, match="ffmpeg executable not found"):
                oc.run_ffmpeg_segment(audio, out_dir, 30.0, ffmpeg_path="/bad/ffmpeg")

    def test_ffmpeg_failure_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        out_dir = tmp_path / "chunks"
        out_dir.mkdir()
        error = subprocess.CalledProcessError(1, "ffmpeg", stderr="boom")
        with patch("subprocess.run", side_effect=error):
            with pytest.raises(TranscriptionError, match="Failed to split oversized audio"):
                oc.run_ffmpeg_segment(audio, out_dir, 30.0, ffmpeg_path="ffmpeg")


class TestSplitAudioForUpload:
    """split_audio_for_upload orchestrates duration, sizing, and retries."""

    def _split(self, audio: Path, **overrides):
        params = {
            "ffmpeg_path": "ffmpeg",
            "ffprobe_path": "ffprobe",
            "max_upload_bytes": 1000,
            "chunk_target_bytes": 900,
            "chunk_min_duration_seconds": 1.0,
        }
        params.update(overrides)
        return oc.split_audio_for_upload(audio, **params)

    def test_unknown_duration_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        with patch.object(oc, "get_audio_duration", return_value=0.0):
            with pytest.raises(TranscriptionError, match="unknown duration"):
                self._split(audio)

    def test_no_chunks_created_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)
        with (
            patch.object(oc, "get_audio_duration", return_value=10.0),
            patch.object(oc, "run_ffmpeg_segment"),  # creates nothing
        ):
            with pytest.raises(TranscriptionError, match="did not create any audio chunks"):
                self._split(audio)

    def test_returns_chunks_within_limit(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)

        def fake_segment(_audio, output_dir, _duration, *, ffmpeg_path):
            (output_dir / "chunk_0000.wav").write_bytes(b"x" * 100)

        with (
            patch.object(oc, "get_audio_duration", return_value=10.0),
            patch.object(oc, "run_ffmpeg_segment", side_effect=fake_segment),
        ):
            chunks = self._split(audio, max_upload_bytes=1000)

        assert len(chunks) == 1
        assert chunks[0].name == "chunk_0000.wav"
        oc.cleanup_chunk_dir(chunks[0].parent)

    def test_shrinks_below_minimum_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)

        def fake_segment(_audio, output_dir, _duration, *, ffmpeg_path):
            (output_dir / "chunk_0000.wav").write_bytes(b"x" * 5000)

        with (
            patch.object(oc, "get_audio_duration", return_value=10.0),
            patch.object(oc, "run_ffmpeg_segment", side_effect=fake_segment),
        ):
            with pytest.raises(TranscriptionError, match="below OpenAI upload limit"):
                self._split(audio, max_upload_bytes=100, chunk_min_duration_seconds=100.0)

    def test_exhausts_retries_raises(self, tmp_path: Path) -> None:
        audio = _make_audio(tmp_path)

        def fake_segment(_audio, output_dir, _duration, *, ffmpeg_path):
            (output_dir / "chunk_0000.wav").write_bytes(b"x" * 5000)

        with (
            patch.object(oc, "get_audio_duration", return_value=10.0),
            patch.object(oc, "run_ffmpeg_segment", side_effect=fake_segment),
        ):
            # chunk_min 0 keeps next_duration above the floor every round, so the
            # loop runs out of attempts instead of shrinking below the minimum.
            with pytest.raises(TranscriptionError, match="after retries"):
                self._split(audio, max_upload_bytes=100, chunk_min_duration_seconds=0.0)


class TestCleanupHelpers:
    """cleanup helpers remove chunk files and the chunk directory."""

    def test_cleanup_files_leaves_directory(self, tmp_path: Path) -> None:
        (tmp_path / "chunk_0000.wav").write_bytes(b"x")
        (tmp_path / "keep.txt").write_bytes(b"y")
        oc.cleanup_chunk_files(tmp_path)
        assert not (tmp_path / "chunk_0000.wav").exists()
        assert (tmp_path / "keep.txt").exists()

    def test_cleanup_dir_removes_directory(self, tmp_path: Path) -> None:
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        (chunk_dir / "chunk_0000.wav").write_bytes(b"x")
        oc.cleanup_chunk_dir(chunk_dir)
        assert not chunk_dir.exists()
