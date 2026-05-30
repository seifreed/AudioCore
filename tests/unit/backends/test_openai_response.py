"""Unit tests for OpenAI response normalization error handling.

The happy-path normalization is exercised through the OpenAI backend tests;
this module pins the failure boundary where a malformed response is wrapped
in a typed TranscriptionError (with API-key redaction applied to the message).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from audiocore.backends.openai_response import parse_transcription_response
from audiocore.errors import TranscriptionError
from audiocore.models import TranscriptionOptions


def test_malformed_segment_raises_transcription_error() -> None:
    """A segment missing its start time fails float() and is wrapped, redacted."""
    # 'start' is absent -> float(None) raises TypeError inside the parser.
    response = {"segments": [{"end": 1.0, "text": "hi"}]}

    def _redact(text: str) -> str:
        return text.replace("secret", "***")

    with pytest.raises(TranscriptionError) as exc_info:
        parse_transcription_response(
            response,
            Path("clip.wav"),
            TranscriptionOptions(),
            processing_time_seconds=0.0,
            redact=_redact,
        )

    assert exc_info.value.context["backend"] == "openai"
    assert exc_info.value.context["file_path"] == "clip.wav"
    assert isinstance(exc_info.value.__cause__, TypeError)
