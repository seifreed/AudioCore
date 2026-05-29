"""Regression tests for word-level timestamps across both backends.

Covers the v2.0 roadmap "Word-level timestamps" feature:
- The OpenAI response normalizer distributes a flat top-level ``words`` array
  across segments by midpoint overlap.
- The faster-whisper backend normalizes native per-segment word objects.
- ``TranscriptionOptions.word_timestamps`` is threaded into the request params.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
from audiocore.backends.openai_backend import OpenAIBackend, _offset_words
from audiocore.backends.openai_response import parse_transcription_response
from audiocore.models import TranscriptionOptions, Word


def _no_redact(message: str) -> str:
    return message


class TestOpenAIWordDistribution:
    """The normalizer assigns flat top-level words to the right segment."""

    def test_words_assigned_to_segment_by_midpoint(self) -> None:
        """Each word lands in the segment whose span contains its midpoint."""
        response = {
            "duration": 2.0,
            "segments": [
                {"start": 0.0, "end": 1.0, "text": "Hello world"},
                {"start": 1.0, "end": 2.0, "text": "again now"},
            ],
            "words": [
                {"word": "Hello", "start": 0.0, "end": 0.4},
                {"word": "world", "start": 0.4, "end": 1.0},
                {"word": "again", "start": 1.0, "end": 1.5},
                {"word": "now", "start": 1.5, "end": 2.0},
            ],
        }

        result = parse_transcription_response(
            response,
            Path("clip.mp3"),
            TranscriptionOptions(word_timestamps=True),
            processing_time_seconds=0.1,
            redact=_no_redact,
        )

        assert result.segments[0].words is not None
        assert [w.word for w in result.segments[0].words] == ["Hello", "world"]
        assert result.segments[1].words is not None
        assert [w.word for w in result.segments[1].words] == ["again", "now"]

    def test_no_words_array_yields_none(self) -> None:
        """Without a top-level words array, segment.words stays None."""
        response = {
            "duration": 1.0,
            "segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}],
        }

        result = parse_transcription_response(
            response,
            Path("clip.mp3"),
            TranscriptionOptions(),
            processing_time_seconds=0.1,
            redact=_no_redact,
        )

        assert result.segments[0].words is None

    def test_offset_words_shifts_timeline(self) -> None:
        """_offset_words shifts per-chunk word timings into the combined timeline."""
        words = [Word(word="hi", start_time=0.0, end_time=0.5, confidence=0.9)]
        shifted = _offset_words(words, 10.0)
        assert shifted is not None
        assert shifted[0].start_time == 10.0
        assert shifted[0].end_time == 10.5
        assert shifted[0].confidence == 0.9

    def test_offset_words_none_passthrough(self) -> None:
        """_offset_words returns None when there are no words to shift."""
        assert _offset_words(None, 5.0) is None


class TestOpenAIRequestParams:
    """word_timestamps adds the granularities param to the API request."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_word_timestamps_requests_granularities(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Enabling word_timestamps sends timestamp_granularities to the SDK."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        audio_file = tmp_path / "clip.mp3"
        audio_file.write_bytes(b"fake audio data")

        response = MagicMock()
        response.segments = []
        response.words = []
        response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = response

        backend = OpenAIBackend(api_key="sk-test123")
        backend.transcribe(audio_file, TranscriptionOptions(word_timestamps=True))

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["timestamp_granularities"] == ["segment", "word"]

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_default_omits_granularities(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """By default no timestamp_granularities param is sent."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        audio_file = tmp_path / "clip.mp3"
        audio_file.write_bytes(b"fake audio data")

        response = MagicMock()
        response.segments = []
        response.words = []
        response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = response

        backend = OpenAIBackend(api_key="sk-test123")
        backend.transcribe(audio_file, TranscriptionOptions())

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert "timestamp_granularities" not in call_kwargs


class TestFasterWhisperWordExtraction:
    """faster-whisper native word objects are normalized into Word models."""

    def test_extract_words_normalizes_probability(self) -> None:
        """probability maps to confidence; word text and timing are preserved."""
        segment = SimpleNamespace(
            words=[
                SimpleNamespace(word=" Hello", start=0.0, end=0.5, probability=0.99),
                SimpleNamespace(word=" world", start=0.5, end=1.0, probability=0.80),
            ]
        )
        words = FasterWhisperBackend._extract_words(segment)
        assert words is not None
        assert [w.word for w in words] == [" Hello", " world"]
        assert words[0].confidence == 0.99

    def test_extract_words_clamps_negative_start(self) -> None:
        """A tiny negative start time is clamped to 0 to satisfy the model."""
        segment = SimpleNamespace(
            words=[SimpleNamespace(word="hi", start=-0.001, end=0.5, probability=0.9)]
        )
        words = FasterWhisperBackend._extract_words(segment)
        assert words is not None
        assert words[0].start_time == 0.0

    def test_extract_words_none_when_absent(self) -> None:
        """When word timestamps were not produced, returns None."""
        assert FasterWhisperBackend._extract_words(SimpleNamespace(words=None)) is None

    def test_build_transcribe_params_honors_option_override(self) -> None:
        """An explicit options.word_timestamps overrides the backend config."""
        backend = FasterWhisperBackend()
        params = backend._build_transcribe_params(TranscriptionOptions(word_timestamps=True))
        assert params["word_timestamps"] is True
