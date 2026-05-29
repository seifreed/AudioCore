"""Unit tests for the TranscriptionTask enum."""

import pytest

from audiocore.types import TranscriptionTask


class TestTranscriptionTaskParse:
    """Tests for TranscriptionTask.parse()."""

    def test_parse_transcribe(self) -> None:
        """Parse the transcribe task from its canonical value."""
        assert TranscriptionTask.parse("transcribe") is TranscriptionTask.TRANSCRIBE

    def test_parse_translate_case_insensitive(self) -> None:
        """Parse the translate task case-insensitively with surrounding space."""
        assert TranscriptionTask.parse("  TRANSLATE ") is TranscriptionTask.TRANSLATE

    def test_parse_invalid_raises(self) -> None:
        """An unknown task raises ValueError listing the valid options."""
        with pytest.raises(ValueError, match="Invalid transcription task"):
            TranscriptionTask.parse("summarize")

    def test_default_value_is_transcribe(self) -> None:
        """The enum's string values match Whisper's task names."""
        assert TranscriptionTask.TRANSCRIBE.value == "transcribe"
        assert TranscriptionTask.TRANSLATE.value == "translate"
