"""Unit tests for format validation in audiocore.media.formats.

These tests verify the format constants and validation functions
without needing real media files.
"""

from pathlib import Path

import pytest

from audiocore.errors.input import MediaFormatError
from audiocore.media.formats import (
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
    is_format_supported,
    validate_format_or_raise,
)

# ============================================================================
# Test format constants
# ============================================================================


class TestSupportedAudioFormats:
    """Tests for SUPPORTED_AUDIO_FORMATS constant."""

    def test_supported_audio_formats_value(self) -> None:
        """Verify SUPPORTED_AUDIO_FORMATS contains expected formats."""
        expected = {"mp3", "wav", "m4a", "flac", "ogg", "aac"}
        assert SUPPORTED_AUDIO_FORMATS == expected

    def test_supported_audio_formats_is_frozenset(self) -> None:
        """Verify SUPPORTED_AUDIO_FORMATS is immutable frozenset."""
        assert isinstance(SUPPORTED_AUDIO_FORMATS, frozenset)

    def test_audio_formats_count(self) -> None:
        """Verify correct number of audio formats."""
        assert len(SUPPORTED_AUDIO_FORMATS) == 6


class TestSupportedVideoFormats:
    """Tests for SUPPORTED_VIDEO_FORMATS constant."""

    def test_supported_video_formats_value(self) -> None:
        """Verify SUPPORTED_VIDEO_FORMATS contains expected formats."""
        expected = {"mp4", "mkv", "avi", "mov", "webm"}
        assert SUPPORTED_VIDEO_FORMATS == expected

    def test_supported_video_formats_is_frozenset(self) -> None:
        """Verify SUPPORTED_VIDEO_FORMATS is immutable frozenset."""
        assert isinstance(SUPPORTED_VIDEO_FORMATS, frozenset)

    def test_video_formats_count(self) -> None:
        """Verify correct number of video formats."""
        assert len(SUPPORTED_VIDEO_FORMATS) == 5


class TestSupportedFormats:
    """Tests for SUPPORTED_FORMATS constant."""

    def test_all_formats_is_union(self) -> None:
        """Verify SUPPORTED_FORMATS is union of audio and video formats."""
        expected = SUPPORTED_AUDIO_FORMATS | SUPPORTED_VIDEO_FORMATS
        assert SUPPORTED_FORMATS == expected

    def test_supported_formats_is_frozenset(self) -> None:
        """Verify SUPPORTED_FORMATS is immutable frozenset."""
        assert isinstance(SUPPORTED_FORMATS, frozenset)

    def test_all_formats_count(self) -> None:
        """Verify correct total number of formats."""
        assert len(SUPPORTED_FORMATS) == len(SUPPORTED_AUDIO_FORMATS) + len(SUPPORTED_VIDEO_FORMATS)


# ============================================================================
# Test is_format_supported()
# ============================================================================


class TestIsFormatSupported:
    """Tests for is_format_supported() function."""

    def test_is_format_supported_returns_true_for_mp3(self) -> None:
        """MP3 files should be recognized as supported."""
        assert is_format_supported("audio.mp3") is True
        assert is_format_supported("/path/to/audio.mp3") is True

    def test_is_format_supported_returns_true_for_mp4(self) -> None:
        """MP4 files should be recognized as supported."""
        assert is_format_supported("video.mp4") is True
        assert is_format_supported("/path/to/video.mp4") is True

    def test_is_format_supported_returns_false_for_unsupported(self) -> None:
        """Unsupported formats should return False."""
        assert is_format_supported("document.pdf") is False
        assert is_format_supported("archive.zip") is False
        assert is_format_supported("script.py") is False

    def test_is_format_supported_case_insensitive(self) -> None:
        """Format detection should be case-insensitive."""
        assert is_format_supported("audio.MP3") is True
        assert is_format_supported("audio.Mp3") is True
        assert is_format_supported("audio.Mp3") is True
        assert is_format_supported("VIDEO.MP4") is True
        assert is_format_supported("video.MOV") is True
        assert is_format_supported("audio.FLAC") is True

    def test_is_format_supported_handles_path_object(self) -> None:
        """is_format_supported should work with Path objects."""
        assert is_format_supported(Path("audio.mp3")) is True
        assert is_format_supported(Path("/path/to/audio.mp3")) is True
        assert is_format_supported(Path("video.mkv")) is True
        assert is_format_supported(Path("document.pdf")) is False

    def test_is_format_supported_handles_string(self) -> None:
        """is_format_supported should work with string paths."""
        assert is_format_supported("audio.mp3") is True
        assert is_format_supported("video.mp4") is True
        assert is_format_supported("document.txt") is False

    def test_is_format_supported_all_audio_formats(self) -> None:
        """All audio formats should be recognized."""
        for fmt in SUPPORTED_AUDIO_FORMATS:
            assert is_format_supported(f"audio.{fmt}") is True, f"{fmt} should be supported"

    def test_is_format_supported_all_video_formats(self) -> None:
        """All video formats should be recognized."""
        for fmt in SUPPORTED_VIDEO_FORMATS:
            assert is_format_supported(f"video.{fmt}") is True, f"{fmt} should be supported"

    def test_is_format_supported_no_extension(self) -> None:
        """Files without extension should return False."""
        assert is_format_supported("noextension") is False
        assert is_format_supported(Path("noextension")) is False

    def test_is_format_supported_multiple_dots(self) -> None:
        """Files with multiple dots should use last extension."""
        assert is_format_supported("audio.backup.mp3") is True
        assert is_format_supported("file.tar.gz") is False
        assert is_format_supported("video.final.mp4") is True


# ============================================================================
# Test validate_format_or_raise()
# ============================================================================


class TestValidateFormatOrRaise:
    """Tests for validate_format_or_raise() function."""

    def test_validate_format_or_raise_passes_for_mp3(self) -> None:
        """MP3 files should not raise error."""
        # Should not raise any exception
        validate_format_or_raise("audio.mp3")
        validate_format_or_raise(Path("audio.mp3"))

    def test_validate_format_or_raise_passes_for_mp4(self) -> None:
        """MP4 files should not raise error."""
        validate_format_or_raise("video.mp4")
        validate_format_or_raise(Path("video.mp4"))

    def test_validate_format_or_raise_passes_for_all_audio_formats(self) -> None:
        """All audio formats should pass validation."""
        for fmt in SUPPORTED_AUDIO_FORMATS:
            # Should not raise
            validate_format_or_raise(f"audio.{fmt}")

    def test_validate_format_or_raise_passes_for_all_video_formats(self) -> None:
        """All video formats should pass validation."""
        for fmt in SUPPORTED_VIDEO_FORMATS:
            # Should not raise
            validate_format_or_raise(f"video.{fmt}")

    def test_validate_format_or_raise_raises_for_unsupported(self) -> None:
        """Unsupported formats should raise MediaFormatError."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("document.pdf")

        assert "Unsupported media format" in str(exc_info.value)
        assert "pdf" in str(exc_info.value)

    def test_validate_format_or_raise_includes_suggestions(self) -> None:
        """MediaFormatError should include actionable suggestions."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("file.xyz")

        error = exc_info.value
        assert error.suggestions is not None
        assert len(error.suggestions) > 0

        # Check for helpful suggestions
        suggestion_text = " ".join(error.suggestions).lower()
        assert "convert" in suggestion_text or "supported format" in suggestion_text

    def test_validate_format_or_raise_includes_context(self) -> None:
        """MediaFormatError should include context with file path and format."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("/path/to/file.xyz")

        error = exc_info.value
        assert error.context is not None
        assert "file_path" in error.context
        assert "format" in error.context
        assert "supported_formats" in error.context

        assert error.context["format"] == "xyz"
        assert "/path/to/file.xyz" in error.context["file_path"]

    def test_validate_format_or_raise_case_insensitive(self) -> None:
        """Invalid format detection should work with different cases."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("file.PDF")

        assert exc_info.value.context["format"] == "pdf"

    def test_validate_format_or_raise_handles_path_object(self) -> None:
        """validate_format_or_raise should work with Path objects."""
        # Valid format should not raise
        validate_format_or_raise(Path("audio.mp3"))

        # Invalid format should raise with correct path in context
        test_path = Path("/path/to/file.xyz")
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise(test_path)

        assert (
            str(test_path) in str(exc_info.value.context["file_path"])
            or Path(exc_info.value.context["file_path"]) == test_path
        )

    def test_validate_format_or_raise_lists_all_supported_formats(self) -> None:
        """Error should list all supported formats in context."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("file.xyz")

        supported = exc_info.value.context["supported_formats"]
        # Should be a sorted list
        assert isinstance(supported, list)
        assert set(supported) == SUPPORTED_FORMATS


# ============================================================================
# Test MediaFormatError integration
# ============================================================================


class TestMediaFormatErrorIntegration:
    """Tests for MediaFormatError raised by format validation."""

    def test_error_contains_supported_formats_list(self) -> None:
        """Error should include sorted list of supported formats."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("file.unknown")

        supported = exc_info.value.context["supported_formats"]
        assert isinstance(supported, list)
        assert "mp3" in supported
        assert "mp4" in supported
        assert "wav" in supported

        # Should be sorted
        assert supported == sorted(supported)

    def test_error_suggestions_are_actionable(self) -> None:
        """Error suggestions should provide actionable guidance."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("video.xyz")

        error = exc_info.value
        assert error.suggestions is not None
        assert len(error.suggestions) >= 2

        # Suggestions should mention conversion
        has_convert_suggestion = any("convert" in s.lower() for s in error.suggestions)
        assert has_convert_suggestion, "Should suggest converting to supported format"

    def test_error_message_includes_format(self) -> None:
        """Error message should clearly indicate the unsupported format."""
        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise("media.rm")

        error_message = str(exc_info.value)
        assert "rm" in error_message  # Format name should appear
        assert "unsupported" in error_message.lower()

    def test_error_context_preserves_file_path(self) -> None:
        """Error context should preserve original file path."""
        test_path = "/some/long/path/to/file.xyz"

        with pytest.raises(MediaFormatError) as exc_info:
            validate_format_or_raise(test_path)

        assert exc_info.value.context["file_path"] == test_path


# ============================================================================
# Test parametrized cases
# ============================================================================


@pytest.mark.parametrize("format_name", ["mp3", "wav", "m4a", "flac", "ogg", "aac"])
def test_audio_formats_are_supported(format_name: str) -> None:
    """All declared audio formats should pass validation."""
    assert is_format_supported(f"file.{format_name}") is True


@pytest.mark.parametrize("format_name", ["mp4", "mkv", "avi", "mov", "webm"])
def test_video_formats_are_supported(format_name: str) -> None:
    """All declared video formats should pass validation."""
    assert is_format_supported(f"file.{format_name}") is True


@pytest.mark.parametrize(
    "format_name,extension",
    [
        ("pdf", "pdf"),
        ("docx", "docx"),
        ("tar", "tar"),
        ("gzip", "gz"),
        ("python", "py"),
        ("javascript", "js"),
    ],
)
def test_non_media_formats_not_supported(format_name: str, extension: str) -> None:
    """Non-media formats should not be supported."""
    assert is_format_supported(f"file.{extension}") is False

    with pytest.raises(MediaFormatError):
        validate_format_or_raise(f"file.{extension}")
