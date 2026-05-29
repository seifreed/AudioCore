"""Regression tests for the streaming transcription API (v2.0 roadmap).

Covers:
- The base backend's default ``transcribe_stream`` (materialize then yield),
  exercised through the OpenAI backend which does not override it.
- faster-whisper's lazy ``transcribe_stream`` override that yields each segment
  as the underlying generator decodes it.
- The public ``stream_transcribe`` is exported and is a generator function.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
from audiocore.backends.openai_backend import OpenAIBackend
from audiocore.models import Segment, TranscriptionOptions


class TestDefaultStreamFallback:
    """The base default streams by yielding a completed transcription's segments."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_openai_stream_yields_all_segments(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """OpenAI (no override) streams every segment from the finished response."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        audio_file = tmp_path / "clip.mp3"
        audio_file.write_bytes(b"fake audio data")

        seg1 = MagicMock(start=0.0, end=2.0, text="Hello")
        seg2 = MagicMock(start=2.0, end=4.0, text="world")
        response = MagicMock()
        response.segments = [seg1, seg2]
        response.words = []
        response.duration = 4.0
        mock_client.audio.transcriptions.create.return_value = response

        backend = OpenAIBackend(api_key="sk-test123")
        produced = list(backend.transcribe_stream(audio_file, TranscriptionOptions()))

        assert [s.text for s in produced] == ["Hello", "world"]
        assert all(isinstance(s, Segment) for s in produced)


class TestFasterWhisperLazyStream:
    """faster-whisper yields segments lazily from its decode generator."""

    def test_stream_yields_segments_incrementally(self, tmp_path: Path) -> None:
        """Each decoded segment is surfaced as a Segment, in order."""
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        decoded: list[str] = []

        def lazy_segments() -> object:
            for spec in [(0.0, 2.0, "First"), (2.0, 4.0, "Second")]:
                decoded.append(spec[2])
                yield MagicMock(start=spec[0], end=spec[1], text=f" {spec[2]} ")

        mock_model = MagicMock()
        mock_model.transcribe.return_value = (lazy_segments(), MagicMock(duration=4.0))
        mock_manager = MagicMock()
        mock_whisper_class = MagicMock(return_value=mock_model)

        with (
            patch(
                "audiocore.backends.faster_whisper_backend.ModelManager",
                return_value=mock_manager,
            ),
            patch.dict(sys.modules, {"faster_whisper": MagicMock(WhisperModel=mock_whisper_class)}),
        ):
            backend = FasterWhisperBackend()
            stream = backend.transcribe_stream(str(audio_file), TranscriptionOptions())

            # Nothing decoded until the first segment is pulled (laziness).
            assert decoded == []
            first = next(stream)
            assert first.text == "First"
            assert decoded == ["First"]
            rest = list(stream)

        assert [s.text for s in rest] == ["Second"]


class TestPublicStreamExport:
    """The public stream_transcribe is wired through the package surface."""

    def test_stream_transcribe_is_exported(self) -> None:
        """audiocore.stream_transcribe resolves to the api function."""
        import audiocore
        from audiocore.api.transcribe import stream_transcribe as api_stream

        assert audiocore.stream_transcribe is api_stream

    def test_stream_transcribe_is_generator_function(self) -> None:
        """stream_transcribe is a generator function (returns a lazy iterator)."""
        import inspect

        from audiocore.api.transcribe import stream_transcribe

        assert inspect.isgeneratorfunction(stream_transcribe)
