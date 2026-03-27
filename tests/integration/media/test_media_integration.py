"""Integration tests for media module with real media files.

These tests use ffmpeg/ffprobe for real file processing.
Tests are skipped if ffmpeg/ffprobe are not available.
"""

import subprocess
from pathlib import Path

import pytest

from audiocore.errors.input import MediaFormatError
from audiocore.media import (
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
    extract_audio,
    is_format_supported,
    probe,
    validate_format_or_raise,
)

# Fixture directory for test media files
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "media"


def ffprobe_available() -> bool:
    """Check if ffprobe is available on system."""
    try:
        subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def ffmpeg_available() -> bool:
    """Check if ffmpeg is available on system."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# Skip markers
requires_ffprobe = pytest.mark.skipif(not ffprobe_available(), reason="ffprobe not available")

requires_ffmpeg = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not available")


def has_fixture_file(filename: str) -> bool:
    """Check if fixture file exists."""
    return (FIXTURES_DIR / filename).exists()


# ============================================================================
# Integration tests for probe()
# ============================================================================


@requires_ffprobe
class TestProbeIntegration:
    """Integration tests for probe() function with real media files."""

    @pytest.mark.skipif(not has_fixture_file("test.mp3"), reason="test.mp3 fixture not available")
    def test_probe_real_mp3_file(self) -> None:
        """Test probing a real MP3 file."""
        mp3_path = FIXTURES_DIR / "test.mp3"
        result = probe(mp3_path)

        assert result.format_name == "mp3"
        assert result.processing_time_seconds > 0
        assert result.sample_rate is not None
        assert result.sample_rate > 0

    @pytest.mark.skipif(not has_fixture_file("test.wav"), reason="test.wav fixture not available")
    def test_probe_real_wav_file(self) -> None:
        """Test probing a real WAV file."""
        wav_path = FIXTURES_DIR / "test.wav"
        result = probe(wav_path)

        assert result.format_name == "wav"
        assert result.processing_time_seconds > 0

    @pytest.mark.skipif(not has_fixture_file("test.mp4"), reason="test.mp4 fixture not available")
    def test_probe_real_mp4_file(self) -> None:
        """Test probing a real MP4 file."""
        mp4_path = FIXTURES_DIR / "test.mp4"
        result = probe(mp4_path)

        # MP4 may have video stream
        assert result.format_name in {"mov,mp4,m4a,3gp,3g2,mj2", "mp4"}
        assert result.processing_time_seconds > 0

    def test_probe_missing_file(self) -> None:
        """Test probing a non-existent file raises error."""
        missing_path = Path("/nonexistent/audio.mp3")

        with pytest.raises(Exception):  # Will raise InvalidInputError or similar
            probe(missing_path)


# ============================================================================
# Integration tests for extract_audio()
# ============================================================================


@requires_ffmpeg
class TestExtractAudioIntegration:
    """Integration tests for extract_audio() function with real media files."""

    @pytest.mark.skipif(not has_fixture_file("test.mp3"), reason="test.mp3 fixture not available")
    def test_extract_real_mp3_to_wav(self, tmp_path: Path) -> None:
        """Test extracting audio from real MP3 file."""
        output_path = tmp_path / "output.wav"
        mp3_path = FIXTURES_DIR / "test.mp3"

        extract_audio(mp3_path, output_path)

        assert output_path.exists()
        # Verify it's a valid WAV by probing
        probe_result = probe(output_path)
        assert probe_result.format_name == "wav"

    @pytest.mark.skipif(not has_fixture_file("test.mp4"), reason="test.mp4 fixture not available")
    def test_extract_mp4_to_wav(self, tmp_path: Path) -> None:
        """Test extracting audio from MP4 file to WAV."""
        output_path = tmp_path / "output.wav"
        mp4_path = FIXTURES_DIR / "test.mp4"

        extract_audio(mp4_path, output_path)

        assert output_path.exists()
        probe_result = probe(output_path)
        assert probe_result.format_name == "wav"

    @pytest.mark.skipif(not has_fixture_file("test.mp3"), reason="test.mp3 fixture not available")
    def test_extract_with_start_time(self, tmp_path: Path) -> None:
        """Test extracting audio with start time offset."""
        output_path = tmp_path / "output.wav"
        mp3_path = FIXTURES_DIR / "test.mp3"

        extract_audio(mp3_path, output_path, start_time_seconds=1.0)

        assert output_path.exists()
        # Duration should be shorter than original if we skipped beginning
        # (assuming test file is > 1 second)

    @pytest.mark.skipif(not has_fixture_file("test.mp3"), reason="test.mp3 fixture not available")
    def test_extract_with_duration(self, tmp_path: Path) -> None:
        """Test extracting audio with duration limit."""
        output_path = tmp_path / "output.wav"
        mp3_path = FIXTURES_DIR / "test.mp3"

        extract_audio(mp3_path, output_path, processing_time_seconds=2.0)

        assert output_path.exists()
        probe_result = probe(output_path)
        # Should be approximately 2 seconds (or slightly less due to encoding)
        assert probe_result.processing_time_seconds <= 2.5  # Allow some tolerance


# ============================================================================
# Integration tests for format validation
# ============================================================================


class TestFormatValidationIntegration:
    """Integration tests for format validation functions."""

    def test_all_audio_formats_supported(self) -> None:
        """Verify all expected audio formats are in SUPPORTED_AUDIO_FORMATS."""
        expected = {"mp3", "wav", "m4a", "flac", "ogg", "aac"}
        assert SUPPORTED_AUDIO_FORMATS == expected

    def test_all_video_formats_supported(self) -> None:
        """Verify all expected video formats are in SUPPORTED_VIDEO_FORMATS."""
        expected = {"mp4", "mkv", "avi", "mov", "webm"}
        assert SUPPORTED_VIDEO_FORMATS == expected

    def test_supported_formats_is_union(self) -> None:
        """Verify SUPPORTED_FORMATS contains both audio and video formats."""
        expected = SUPPORTED_AUDIO_FORMATS | SUPPORTED_VIDEO_FORMATS
        assert SUPPORTED_FORMATS == expected

    def test_unsupported_format_raises_error(self) -> None:
        """Test that unsupported format raises MediaFormatError."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("document.pdf")

        assert "Unsupported media format" in str(exc_info.value)
        assert "pdf" in str(exc_info.value)
        assert exc_info.value.context is not None
        assert "supported_formats" in exc_info.value.context

    def test_case_insensitive_format_detection(self) -> None:
        """Test that format detection works with different cases."""
        assert is_format_supported("audio.MP3") is True
        assert is_format_supported("audio.Mp3") is True
        assert is_format_supported("audio.mp3") is True
        assert is_format_supported("video.MP4") is True
        assert is_format_supported("video.MOV") is True

    def test_supported_format_does_not_raise(self) -> None:
        """Test that supported format does not raise error."""
        # Should not raise any exception
        validate_format_or_raise("audio.mp3")
        validate_format_or_raise("video.mp4")
        validate_format_or_raise("audio.flac")

    def test_all_expected_formats_in_supported(self) -> None:
        """Verify all expected formats are recognized."""
        audio_formats = ["mp3", "wav", "m4a", "flac", "ogg", "aac"]
        video_formats = ["mp4", "mkv", "avi", "mov", "webm"]

        for fmt in audio_formats:
            assert is_format_supported(f"file.{fmt}"), f"{fmt} should be supported"

        for fmt in video_formats:
            assert is_format_supported(f"file.{fmt}"), f"{fmt} should be supported"

    @pytest.mark.parametrize(
        "unsupported_format", ["xyz", "pdf", "doc", "exe", "txt", "csv", "json", "xml"]
    )
    def test_unsupported_formats_not_in_supported(self, unsupported_format: str) -> None:
        """Test that non-media formats are not supported."""
        assert is_format_supported(f"file.{unsupported_format}") is False
