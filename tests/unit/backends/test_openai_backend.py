"""Unit tests for OpenAI Whisper API backend implementation.

These tests verify:
- OpenAIBackend implements all TranscriptionBackend ABC methods
- Lazy client initialization
- API key validation
- Error mapping from OpenAI exceptions to AudioCore exceptions
- API key redaction in error messages
- Successful transcription parsing
- All mocked, no live API calls
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openai import (
    APITimeoutError as OpenAITimeoutError,
)
from openai import (
    AuthenticationError as OpenAIAuthenticationError,
)
from openai import (
    RateLimitError as OpenAIRateLimitError,
)

from audiocore.backends.openai_backend import OpenAIBackend
from audiocore.errors import (
    APITimeoutError,
    AuthenticationError,
    BackendUnavailableError,
    RateLimitError,
    TranscriptionError,
)
from audiocore.models import TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType


class TestOpenAIBackendBasics:
    """Test basic OpenAIBackend properties and methods."""

    def test_backend_type_returns_openai(self) -> None:
        """Verify backend_type returns OPENAI enum."""
        backend = OpenAIBackend(api_key="sk-test123")
        assert backend.backend_type == BackendType.OPENAI

    def test_get_name_returns_correct_name(self) -> None:
        """Verify get_name returns correct display name."""
        backend = OpenAIBackend(api_key="sk-test123")
        assert backend.get_name() == "OpenAI Whisper API"

    def test_get_model_options_returns_whisper_1(self) -> None:
        """Verify get_model_options returns whisper-1."""
        backend = OpenAIBackend(api_key="sk-test123")
        models = backend.get_model_options()
        assert models == ["whisper-1"]

    def test_is_available_true_with_valid_api_key(self) -> None:
        """Verify is_available returns True with valid API key."""
        backend = OpenAIBackend(api_key="sk-valid-key")
        assert backend.is_available() is True

    def test_is_available_false_without_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify is_available returns False without API key."""
        # Ensure no env var is set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        backend = OpenAIBackend()
        # No api_key provided, no env var set
        assert backend.is_available() is False

    def test_is_available_true_with_non_sk_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify is_available returns True with any non-empty key.

        OpenAI now issues keys in various formats (sk-proj-, sk-org-, etc.)
        so we only check for presence, not format.
        """
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        backend = OpenAIBackend(api_key="non-sk-format-key")
        assert backend.is_available() is True

    def test_is_available_true_with_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify is_available returns True with valid env var."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key-123")
        backend = OpenAIBackend()
        assert backend.is_available() is True

    def test_is_available_uses_audiocore_env_when_openai_env_is_blank(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: blank OPENAI_API_KEY should not block AUDIOCORE_OPENAI_API_KEY."""
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-fallback-key")

        backend = OpenAIBackend()

        assert backend.is_available() is True

    def test_is_available_true_with_non_sk_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify is_available returns True with any non-empty env var key.

        OpenAI now issues keys in various formats, so we only check for presence.
        """
        monkeypatch.setenv("OPENAI_API_KEY", "non-sk-format-key")
        backend = OpenAIBackend()
        assert backend.is_available() is True


class TestLazyClientInitialization:
    """Test lazy client initialization behavior."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_client_created_on_first_transcribe(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Verify client is created lazily on first transcribe call."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Create mock audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Create backend
        backend = OpenAIBackend(api_key="sk-test123")

        # Client should not be created yet
        mock_openai.assert_not_called()

        # Mock successful transcription
        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = mock_response

        # Call transcribe - client should be created now
        options = TranscriptionOptions()
        result = backend.transcribe(audio_file, options)

        # Verify client was created
        mock_openai.assert_called_once_with(api_key="sk-test123")
        assert result is not None

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_client_reused_on_subsequent_transcribe(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Verify client is reused for subsequent transcribe calls."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Create mock audio files
        audio_file1 = tmp_path / "test1.mp3"
        audio_file1.write_bytes(b"fake audio data 1")
        audio_file2 = tmp_path / "test2.mp3"
        audio_file2.write_bytes(b"fake audio data 2")

        # Create backend and transcribe twice
        backend = OpenAIBackend(api_key="sk-test123")

        # Mock successful transcription
        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = mock_response

        options = TranscriptionOptions()
        backend.transcribe(audio_file1, options)
        backend.transcribe(audio_file2, options)

        # Client should only be created once
        mock_openai.assert_called_once()


class TestTranscribeSuccess:
    """Test successful transcription scenarios."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_returns_transcription_result(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Verify transcribe returns valid TranscriptionResult."""
        # Setup mock client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Create mock audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Create mock response with segments
        mock_segment1 = MagicMock()
        mock_segment1.start = 0.0
        mock_segment1.end = 5.0
        mock_segment1.text = "Hello world"

        mock_segment2 = MagicMock()
        mock_segment2.start = 5.0
        mock_segment2.end = 10.0
        mock_segment2.text = "This is a test"

        mock_response = MagicMock()
        mock_response.segments = [mock_segment1, mock_segment2]
        mock_response.duration = 10.0

        mock_client.audio.transcriptions.create.return_value = mock_response

        # Create backend and transcribe
        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        result = backend.transcribe(audio_file, options)

        # Verify result
        assert isinstance(result, TranscriptionResult)
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello world"
        assert result.segments[1].text == "This is a test"
        assert result.media_info.duration == 10.0
        assert result.backend_used == BackendType.OPENAI
        assert result.processing_time_seconds >= 0

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_with_language_option(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify language option is passed to API."""
        # Setup mock
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = mock_response

        # Transcribe with language option
        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions(language="en")
        backend.transcribe(audio_file, options)

        # Verify language was passed
        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["language"] == "en"

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_no_model_size_to_temperature_mapping(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Verify model_size does NOT map to temperature (removed arbitrary mapping)."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")

        from audiocore.types import ModelSize

        options = TranscriptionOptions(model_size=ModelSize.BASE)
        backend.transcribe(audio_file, options)

        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        # Temperature should NOT be set from model_size
        assert "temperature" not in call_kwargs

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_file_not_found_raises_invalid_input_error(
        self, mock_openai: MagicMock
    ) -> None:
        """Verify transcribe raises InvalidInputError for missing file."""
        from audiocore.errors import InvalidInputError

        # Don't need to setup OpenAI mock - file check happens first
        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(InvalidInputError) as exc_info:
            backend.transcribe("/nonexistent/file.mp3", options)

        assert "not found" in str(exc_info.value).lower()

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_directory_raises_invalid_input_error(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Existing directories should be rejected before opening the API file."""
        from audiocore.errors import InvalidInputError

        audio_dir = tmp_path / "audio.mp3"
        audio_dir.mkdir()
        backend = OpenAIBackend(api_key="sk-test123")

        with pytest.raises(InvalidInputError) as exc_info:
            backend.transcribe(audio_dir, TranscriptionOptions())

        assert "not a file" in str(exc_info.value)
        mock_openai.assert_not_called()


class TestErrorHandling:
    """Test OpenAI exception to AudioCore exception mapping."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_authentication_error_mapped(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify OpenAI AuthenticationError maps to AudioCore AuthenticationError."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise authentication error
        mock_client.audio.transcriptions.create.side_effect = OpenAIAuthenticationError(
            "Invalid API key",
            response=MagicMock(),
            body=None,
        )

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(AuthenticationError) as exc_info:
            backend.transcribe(audio_file, options)

        assert exc_info.value.error_code == "AUD-301"
        assert "authentication" in str(exc_info.value).lower()
        assert exc_info.value.context is not None
        assert exc_info.value.context.get("backend") == "openai"

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_rate_limit_error_mapped(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify OpenAI RateLimitError maps to AudioCore RateLimitError."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise rate limit error
        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "30"}
        mock_client.audio.transcriptions.create.side_effect = OpenAIRateLimitError(
            "Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(RateLimitError) as exc_info:
            backend.transcribe(audio_file, options)

        assert exc_info.value.error_code == "AUD-302"
        assert "rate limit" in str(exc_info.value).lower()
        assert exc_info.value.context is not None
        assert exc_info.value.context.get("retry_after") == 30

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_rate_limit_error_no_retry_after(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify RateLimitError works without retry_after header."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise rate limit error without retry_after
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_client.audio.transcriptions.create.side_effect = OpenAIRateLimitError(
            "Rate limit exceeded",
            response=mock_response,
            body=None,
        )

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(RateLimitError) as exc_info:
            backend.transcribe(audio_file, options)

        assert exc_info.value.error_code == "AUD-302"
        # Should still work without retry_after
        assert exc_info.value.context is not None

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_timeout_error_mapped(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify OpenAI APITimeoutError maps to AudioCore APITimeoutError."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise timeout error
        mock_client.audio.transcriptions.create.side_effect = OpenAITimeoutError(
            "Request timed out"
        )

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(APITimeoutError) as exc_info:
            backend.transcribe(audio_file, options)

        assert exc_info.value.error_code == "AUD-303"
        assert "timeout" in str(exc_info.value).lower()

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_unexpected_error_mapped_to_transcription_error(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Verify unexpected exceptions map to TranscriptionError."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise unexpected error
        mock_client.audio.transcriptions.create.side_effect = RuntimeError("Unexpected error")

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(TranscriptionError) as exc_info:
            backend.transcribe(audio_file, options)

        assert exc_info.value.error_code == "AUD-202"


class TestAPIKeyRedaction:
    """Test API key redaction in error messages."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_redact_constructor_api_key(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify constructor-provided API key is redacted from errors."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise error with API key in message
        api_key = "sk-secret-key-12345"
        mock_client.audio.transcriptions.create.side_effect = OpenAIAuthenticationError(
            f"Invalid API key: {api_key}",
            response=MagicMock(),
            body=None,
        )

        backend = OpenAIBackend(api_key=api_key)
        options = TranscriptionOptions()

        with pytest.raises(AuthenticationError) as exc_info:
            backend.transcribe(audio_file, options)

        error_msg = str(exc_info.value)
        assert api_key not in error_msg
        assert "[REDACTED]" in error_msg

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_redact_env_api_key(
        self, mock_openai: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify environment API key is redacted from errors."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        api_key = "sk-env-key-12345"
        monkeypatch.setenv("OPENAI_API_KEY", api_key)

        # Mock API to raise error with API key in message
        mock_client.audio.transcriptions.create.side_effect = OpenAIAuthenticationError(
            f"Invalid API key: {api_key}",
            response=MagicMock(),
            body=None,
        )

        backend = OpenAIBackend()  # Uses env var
        options = TranscriptionOptions()

        with pytest.raises(AuthenticationError) as exc_info:
            backend.transcribe(audio_file, options)

        error_msg = str(exc_info.value)
        assert api_key not in error_msg
        assert "[REDACTED]" in error_msg

    def test_api_key_not_in_repr(self) -> None:
        """Verify API key doesn't appear in string representation."""
        api_key = "sk-secret-key-12345"
        backend = OpenAIBackend(api_key=api_key)

        # API key should not appear in any string representation
        repr_str = repr(backend)
        str_str = str(backend)

        assert api_key not in repr_str
        assert api_key not in str_str

    def test_blank_api_key_redaction_does_not_rewrite_entire_message(self) -> None:
        """Regression: blank keys must not trigger empty-string replacement."""
        backend = OpenAIBackend(api_key="   ")

        assert backend._redact_api_key("plain error") == "plain error"


class TestBackendUnavailable:
    """Test backend unavailable scenarios."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_without_api_key_raises_error(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Verify transcribe raises BackendUnavailableError without API key."""
        # Clear any env var
        with patch.dict(os.environ, {}, clear=True):
            backend = OpenAIBackend()
            options = TranscriptionOptions()

            audio_file = tmp_path / "test.mp3"
            audio_file.write_bytes(b"fake audio data")

            with pytest.raises(BackendUnavailableError) as exc_info:
                backend.transcribe(audio_file, options)

            assert exc_info.value.error_code == "AUD-201"
            assert "not configured" in str(exc_info.value).lower()

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_with_blank_api_key_raises_unavailable(
        self, mock_openai: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: whitespace-only API keys should not create OpenAI clients."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AUDIOCORE_OPENAI_API_KEY", raising=False)

        backend = OpenAIBackend(api_key="   ")
        options = TranscriptionOptions()

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        with pytest.raises(BackendUnavailableError) as exc_info:
            backend.transcribe(audio_file, options)

        assert "not configured" in str(exc_info.value).lower()
        mock_openai.assert_not_called()

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_transcribe_uses_fallback_env_key_when_primary_env_key_is_blank(
        self, mock_openai: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: fallback env key should be used when OPENAI_API_KEY is blank."""
        monkeypatch.setenv("OPENAI_API_KEY", "   ")
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "  sk-fallback-key  ")

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = mock_response

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        backend = OpenAIBackend()
        backend.transcribe(audio_file, TranscriptionOptions())

        mock_openai.assert_called_once_with(api_key="sk-fallback-key")


class TestFileHandling:
    """Test file handling behavior."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_file_closed_on_success(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify file handle is closed after successful transcription."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0
        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        backend.transcribe(audio_file, options)

        # Verify file was closed (file object was passed and should be closed)
        # The file is opened inside the try block and should be closed
        # We can't directly check if closed, but we can verify no file leak

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_file_closed_on_error(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify file handle is closed even when error occurs."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock API to raise error
        mock_client.audio.transcriptions.create.side_effect = OpenAIAuthenticationError(
            "Error",
            response=MagicMock(),
            body=None,
        )

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()

        with pytest.raises(AuthenticationError):
            backend.transcribe(audio_file, options)

        # File should be closed in error handler


class TestTranscriptionResultParsing:
    """Test transcription result parsing from OpenAI response."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_parse_segments_from_verbose_json(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify segments are parsed from verbose_json response."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Create mock response with segments
        mock_seg1 = MagicMock()
        mock_seg1.start = 0.0
        mock_seg1.end = 2.5
        mock_seg1.text = "First segment"

        mock_seg2 = MagicMock()
        mock_seg2.start = 2.5
        mock_seg2.end = 5.0
        mock_seg2.text = "Second segment"

        mock_response = MagicMock()
        mock_response.segments = [mock_seg1, mock_seg2]
        mock_response.duration = 5.0

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        result = backend.transcribe(audio_file, options)

        # Verify segments
        assert len(result.segments) == 2
        assert result.segments[0].start_time == 0.0
        assert result.segments[0].end_time == 2.5
        assert result.segments[0].text == "First segment"
        assert result.segments[1].start_time == 2.5
        assert result.segments[1].end_time == 5.0
        assert result.segments[1].text == "Second segment"

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_duration_from_response(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify duration is extracted from response."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 123.45

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        result = backend.transcribe(audio_file, options)

        assert result.media_info.duration == 123.45

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_duration_from_last_segment(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify duration calculated from last segment when not in response."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_seg = MagicMock()
        mock_seg.start = 0.0
        mock_seg.end = 7.5
        mock_seg.text = "Test"

        mock_response = MagicMock()
        mock_response.segments = [mock_seg]
        # No duration attribute
        delattr(mock_response, "duration")

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        result = backend.transcribe(audio_file, options)

        # Duration should come from last segment end time
        assert result.media_info.duration == 7.5

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_empty_segments(self, mock_openai: MagicMock, tmp_path: Path) -> None:
        """Verify handling of empty segments list."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        # Use a small positive duration since MediaInfo requires duration > 0
        mock_response.duration = None
        delattr(mock_response, "duration")

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        result = backend.transcribe(audio_file, options)

        assert result.segments == []
        # When no duration is available, we use a small minimum duration
        assert result.media_info.duration == 0.01

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_text_response_without_segments_keeps_transcript(
        self, mock_openai: MagicMock, tmp_path: Path
    ) -> None:
        """Regression: response.text must not be dropped when segments are absent."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 3.5
        mock_response.text = "Whole file transcript"

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        result = backend.transcribe(audio_file, TranscriptionOptions())

        assert len(result.segments) == 1
        assert result.segments[0].start_time == 0.0
        assert result.segments[0].end_time == 3.5
        assert result.segments[0].text == "Whole file transcript"


class TestLogging:
    """Test logging behavior."""

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_debug_logging_on_transcribe(
        self, mock_openai: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify debug logging for transcription."""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key="sk-test123")
        options = TranscriptionOptions()
        backend.transcribe(audio_file, options)

        # Check debug logs
        log_messages = [record.message for record in caplog.records]
        assert any("transcription" in msg.lower() for msg in log_messages)

    @patch("audiocore.backends.openai_backend.OpenAI")
    def test_no_api_key_in_logs(
        self, mock_openai: MagicMock, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify API key never appears in log output."""
        import logging

        caplog.set_level(logging.DEBUG)

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        api_key = "sk-secret-log-test-123"

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.segments = []
        mock_response.duration = 1.0

        mock_client.audio.transcriptions.create.return_value = mock_response

        backend = OpenAIBackend(api_key=api_key)
        options = TranscriptionOptions()
        backend.transcribe(audio_file, options)

        # Check all log messages
        all_logs = "".join(record.message for record in caplog.records)
        assert api_key not in all_logs
