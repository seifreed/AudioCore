"""Unit tests for segment-level parallel processing.

Tests verify:
- transcribe_segments_parallel() raises NotImplementedError
- Proper error message guides users to file-level processing
"""

from pathlib import Path

import pytest

from audiocore.models import MediaInfo, Segment, TranscriptionOptions
from audiocore.parallel.segments import transcribe_segments_parallel


class TestTranscribeSegmentsParallel:
    """Test transcribe_segments_parallel placeholder function."""

    def test_raises_not_implemented(self) -> None:
        """Test that function raises NotImplementedError."""
        segments = [Segment(start_time=0.0, end_time=5.0, text="")]
        audio_path = Path("test.wav")
        options = TranscriptionOptions()

        with pytest.raises(NotImplementedError) as exc_info:
            transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=options,
            )

        assert "not yet implemented" in str(exc_info.value).lower()
        assert "segment-level" in str(exc_info.value).lower()

    def test_error_message_suggests_alternative(self) -> None:
        """Test that error message suggests file-level concurrency."""
        segments = [Segment(start_time=0.0, end_time=5.0, text="")]
        audio_path = Path("test.wav")
        options = TranscriptionOptions()

        with pytest.raises(NotImplementedError) as exc_info:
            transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=options,
            )

        error_message = str(exc_info.value).lower()
        assert "file-level" in error_message or "files" in error_message
        assert "transcribe_files_concurrent" in str(exc_info.value)

    def test_accepts_all_parameters(self) -> None:
        """Test that function accepts all documented parameters before raising."""
        segments = [Segment(start_time=0.0, end_time=5.0, text="")]
        audio_path = Path("test.wav")
        options = TranscriptionOptions()
        media_info = MediaInfo(duration=10.0, format="wav", sample_rate=16000, channels=1)

        # Should accept parameters but still raise NotImplementedError
        with pytest.raises(NotImplementedError):
            transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=options,
                max_workers=4,
                media_info=media_info,
            )

    def test_with_multiple_segments(self) -> None:
        """Test with multiple segments."""
        segments = [
            Segment(start_time=0.0, end_time=5.0, text=""),
            Segment(start_time=5.0, end_time=10.0, text=""),
            Segment(start_time=10.0, end_time=15.0, text=""),
        ]
        audio_path = Path("test.wav")
        options = TranscriptionOptions()

        with pytest.raises(NotImplementedError):
            transcribe_segments_parallel(
                segments=segments,
                audio_path=audio_path,
                options=options,
                max_workers=2,
            )

    def test_with_custom_max_workers(self) -> None:
        """Test with different max_workers values."""
        segments = [Segment(start_time=0.0, end_time=5.0, text="")]
        audio_path = Path("test.wav")
        options = TranscriptionOptions()

        # Test with various max_workers
        for max_workers in [1, 4, 8, 16]:
            with pytest.raises(NotImplementedError):
                transcribe_segments_parallel(
                    segments=segments,
                    audio_path=audio_path,
                    options=options,
                    max_workers=max_workers,
                )
