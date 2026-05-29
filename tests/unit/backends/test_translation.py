"""Regression tests for the translation task across both backends.

Covers the v2.0 roadmap "Translation API" feature:
- faster-whisper receives ``task`` in its decode params.
- The OpenAI backend routes the translate task to the translations endpoint
  (which outputs English and accepts neither language nor word granularities).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
from audiocore.backends.openai_backend import OpenAIBackend
from audiocore.models import TranscriptionOptions
from audiocore.types import TranscriptionTask


class TestFasterWhisperTask:
    """faster-whisper forwards the task to its decode parameters."""

    def test_default_task_is_transcribe(self) -> None:
        """The default option produces task='transcribe'."""
        backend = FasterWhisperBackend()
        params = backend._build_transcribe_params(TranscriptionOptions())
        assert params["task"] == "transcribe"

    def test_translate_task_forwarded(self) -> None:
        """A translate option produces task='translate'."""
        backend = FasterWhisperBackend()
        params = backend._build_transcribe_params(
            TranscriptionOptions(task=TranscriptionTask.TRANSLATE)
        )
        assert params["task"] == "translate"


class TestOpenAITranslationEndpoint:
    """The OpenAI backend selects the endpoint matching the task."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_translate_uses_translations_endpoint(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """The translate task calls translations.create, not transcriptions.create."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        audio_file = tmp_path / "clip.mp3"
        audio_file.write_bytes(b"fake audio data")

        response = MagicMock()
        response.segments = []
        response.words = []
        response.duration = 1.0
        mock_client.audio.translations.create.return_value = response

        backend = OpenAIBackend(api_key="sk-test123")
        backend.transcribe(
            audio_file,
            TranscriptionOptions(task=TranscriptionTask.TRANSLATE, language="es"),
        )

        mock_client.audio.translations.create.assert_called_once()
        mock_client.audio.transcriptions.create.assert_not_called()
        # The translations endpoint must not receive a language argument.
        call_kwargs = mock_client.audio.translations.create.call_args[1]
        assert "language" not in call_kwargs
        assert "timestamp_granularities" not in call_kwargs

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_uses_transcriptions_endpoint(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """The default transcribe task calls transcriptions.create."""
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

        mock_client.audio.transcriptions.create.assert_called_once()
        mock_client.audio.translations.create.assert_not_called()
