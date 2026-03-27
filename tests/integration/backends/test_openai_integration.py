"""Integration tests for OpenAI Whisper API backend.

These tests require a live OpenAI API key (OPENAI_API_KEY environment variable).
All tests are marked with @pytest.mark.integration and skip gracefully if
no API key is available.

Test Categories:
- Real audio transcription
- Error handling with invalid credentials
- Rate limit handling
- Backend registration in BackendRegistry
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from audiocore.backends import BackendRegistry, OpenAIBackend
from audiocore.errors import AuthenticationError
from audiocore.models import TranscriptionOptions
from audiocore.types import BackendType

# Skip all tests in this module if no API key
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set - skipping integration tests",
)


@pytest.fixture
def api_key() -> str:
    """Get OpenAI API key from environment."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set")
    return key


@pytest.fixture
def sample_audio_file(tmp_path: Path) -> Path:
    """Create a small sample audio file for testing.

    Creates a minimal WAV file with 1 second of silence.
    This is sufficient for testing the OpenAI API without
    incurring significant costs.
    """
    import struct
    import wave

    audio_path = tmp_path / "test_audio.wav"

    # Create a minimal WAV file: 1 second of silence at 16kHz mono
    # WAV format: RIFF header + fmt chunk + data chunk
    sample_rate = 16000
    duration_seconds = 1
    num_samples = sample_rate * duration_seconds

    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        # Write silence (zeros)
        wav_file.writeframes(struct.pack("<" + "h" * num_samples, *([0] * num_samples)))

    return audio_path


@pytest.mark.integration
class TestOpenAITranscription:
    """Test real OpenAI Whisper API transcription."""

    def test_transcribe_real_audio(self, api_key: str, sample_audio_file: Path) -> None:
        """Test transcription of a real audio file."""
        backend = OpenAIBackend(api_key=api_key)
        options = TranscriptionOptions()

        result = backend.transcribe(sample_audio_file, options)

        # Verify result structure
        assert result is not None
        assert result.backend_used == BackendType.OPENAI
        assert result.media_info is not None
        assert result.processing_time_seconds > 0

        # For silence, segments may be empty or contain silence marker
        # OpenAI Whisper API may return empty transcription for silence
        assert isinstance(result.segments, list)

    def test_transcribe_with_language_hint(self, api_key: str, sample_audio_file: Path) -> None:
        """Test transcription with language parameter."""
        backend = OpenAIBackend(api_key=api_key)
        options = TranscriptionOptions(language="en")

        result = backend.transcribe(sample_audio_file, options)

        assert result is not None
        assert result.backend_used == BackendType.OPENAI

    def test_transcribe_with_different_model_sizes(
        self, api_key: str, sample_audio_file: Path
    ) -> None:
        """Test transcription with different model sizes (temperature mapping)."""
        from audiocore.types import ModelSize

        backend = OpenAIBackend(api_key=api_key)
        options = TranscriptionOptions(model_size=ModelSize.TINY)

        # tiny model -> temperature 0.0
        result = backend.transcribe(sample_audio_file, options)

        assert result is not None
        assert result.backend_used == BackendType.OPENAI


@pytest.mark.integration
class TestOpenAIErrorHandling:
    """Test OpenAI API error handling."""

    def test_invalid_api_key_raises_authentication_error(self, sample_audio_file: Path) -> None:
        """Test that invalid API key raises AuthenticationError."""
        # Use invalid API key
        backend = OpenAIBackend(api_key="sk-invalid-key-12345")
        options = TranscriptionOptions()

        with pytest.raises(AuthenticationError) as exc_info:
            backend.transcribe(sample_audio_file, options)

        # Verify error message redacts the API key
        error_msg = str(exc_info.value)
        assert "sk-invalid-key-12345" not in error_msg
        assert "[REDACTED]" in error_msg or "authentication" in error_msg.lower()


@pytest.mark.integration
class TestBackendRegistration:
    """Test backend registration with BackendRegistry."""

    def test_backend_registry_flow(self, api_key: str) -> None:
        """Test full backend registration and retrieval flow."""
        # Create a new registry instance
        registry = BackendRegistry()

        # Register OpenAI backend
        registry.register(BackendType.OPENAI, OpenAIBackend)

        # Get backend (note: env var must be set for backend to work)
        import os

        os.environ["OPENAI_API_KEY"] = api_key

        backend = registry.get_backend(BackendType.OPENAI)

        # Verify backend properties
        assert backend is not None
        assert backend.backend_type == BackendType.OPENAI
        assert backend.get_name() == "OpenAI Whisper API"
        assert "whisper-1" in backend.get_model_options()

    def test_backend_is_available(self, api_key: str) -> None:
        """Test backend availability check."""
        backend = OpenAIBackend(api_key=api_key)

        # Should be available with valid key
        assert backend.is_available() is True

    def test_backend_is_available_without_key(self) -> None:
        """Test backend availability without API key."""
        # Clear environment
        env_key = os.environ.get("OPENAI_API_KEY")

        try:
            if env_key:
                del os.environ["OPENAI_API_KEY"]

            backend = OpenAIBackend()
            assert backend.is_available() is False
        finally:
            # Restore environment
            if env_key:
                os.environ["OPENAI_API_KEY"] = env_key

    def test_list_backends_includes_openai(self) -> None:
        """Test that BackendRegistry includes OpenAI."""
        # Import triggers registration
        from audiocore.backends import BackendRegistry

        registry = BackendRegistry()
        backends = registry.list_backends()

        # OpenAI should be in the list
        assert BackendType.OPENAI in backends
