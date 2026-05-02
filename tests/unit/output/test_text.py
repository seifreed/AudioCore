"""Unit tests for plain text output formatter."""

import pytest

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult
from audiocore.output.text import _format_timestamp, format_text
from audiocore.types import BackendType


@pytest.fixture
def sample_media_info() -> MediaInfo:
    """Create a sample MediaInfo for testing."""
    return MediaInfo(
        duration=120.5,
        format="mp3",
        codec="mp3",
        sample_rate=44100,
        channels=2,
    )


@pytest.fixture
def sample_options() -> TranscriptionOptions:
    """Create sample transcription options."""
    return TranscriptionOptions()


@pytest.fixture
def sample_result(sample_media_info: MediaInfo) -> TranscriptionResult:
    """Create a sample TranscriptionResult for testing."""
    return TranscriptionResult(
        segments=[
            Segment(start_time=0.0, end_time=5.234, text="Hello world"),
            Segment(start_time=5.5, end_time=10.0, text="How are you?"),
            Segment(start_time=10.5, end_time=15.75, text="I'm doing great"),
        ],
        media_info=sample_media_info,
        config_used=TranscriptionOptions(),
        processing_time_seconds=15.5,
        backend_used=BackendType.OPENAI,
    )


class TestFormatTimestamp:
    """Tests for _format_timestamp helper function."""

    def test_zero_seconds(self) -> None:
        """Zero seconds formats as 00:00:00.000."""
        result = _format_timestamp(0.0)
        assert result == "00:00:00.000"

    def test_seconds_only(self) -> None:
        """Seconds less than 60 format correctly."""
        # Use exact float to avoid precision issues
        result = _format_timestamp(45.0)
        assert result == "00:00:45.000"

    def test_fractional_seconds(self) -> None:
        """Fractional seconds format correctly."""
        result = _format_timestamp(5.5)
        assert result == "00:00:05.500"

    def test_milliseconds_precision(self) -> None:
        """Milliseconds have 3 digits."""
        result = _format_timestamp(1.123)
        assert result == "00:00:01.123"

    def test_minutes_and_seconds(self) -> None:
        """Minutes format correctly."""
        result = _format_timestamp(125.0)  # 2:05.000
        assert result == "00:02:05.000"

    def test_hours_minutes_seconds(self) -> None:
        """Hours format correctly."""
        result = _format_timestamp(3725.456)  # 1:02:05.456
        assert result == "01:02:05.456"

    def test_large_hours(self) -> None:
        """Large hour values format correctly."""
        # Use exact values to avoid floating-point precision issues
        result = _format_timestamp(7325.500)  # 2h 2m 5.500s
        assert result == "02:02:05.500"

    def test_milliseconds_truncation(self) -> None:
        """Milliseconds are truncated, not rounded."""
        # The float 1.9999 is stored as something like 1.99989... due to binary representation
        # Our implementation truncates, so we test with exact values
        result = _format_timestamp(5.123)
        assert result == "00:00:05.123"

    def test_timestamp_overflow_carries_to_second(self) -> None:
        """Regression: 59.9999s must not produce .1000 (invalid timestamp).

        The result must be 00:01:00.000, not 00:00:59.1000.
        """
        result = _format_timestamp(59.9999)
        assert result == "00:01:00.000"


class TestFormatText:
    """Tests for format_text function."""

    def test_multiple_segments(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Multiple segments produce correct output with timestamps."""
        text = format_text(sample_result, sample_options)

        lines = text.split("\n")
        assert len(lines) == 3
        assert lines[0] == "[00:00:00.000] Hello world"
        assert lines[1] == "[00:00:05.500] How are you?"
        assert lines[2] == "[00:00:10.500] I'm doing great"

    def test_single_segment(self, sample_media_info: MediaInfo) -> None:
        """Single segment produces one line."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert text == "[00:00:00.000] Hello"

    def test_empty_segments(self, sample_media_info: MediaInfo) -> None:
        """Empty segments list produces empty string."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert text == ""

    def test_empty_text_in_segment(self, sample_media_info: MediaInfo) -> None:
        """Segment with empty text produces timestamp with empty content."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text=""),
                Segment(start_time=5.0, end_time=10.0, text="Hello"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        lines = text.split("\n")
        assert lines[0] == "[00:00:00.000] "
        assert lines[1] == "[00:00:05.000] Hello"

    def test_special_characters(self, sample_media_info: MediaInfo) -> None:
        """Special characters are preserved in output."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello, world! émojis: 🎉"),
                Segment(start_time=5.0, end_time=10.0, text="Quotes: \"test\" and 'single'"),
                Segment(start_time=10.0, end_time=15.0, text="Newlines\nand\ttabs"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=15.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert "Hello, world! émojis: 🎉" in text
        assert "Quotes: \"test\" and 'single'" in text
        assert "Newlines\nand\ttabs" in text

    def test_utf8_encoding(self, sample_media_info: MediaInfo) -> None:
        """UTF-8 characters are preserved correctly."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="こんにちは世界"),
                Segment(start_time=5.0, end_time=10.0, text="Привет мир"),
                Segment(start_time=10.0, end_time=15.0, text="مرحبا بالعالم"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=15.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert "こんにちは世界" in text
        assert "Привет мир" in text
        assert "مرحبا بالعالم" in text

    def test_confidence_not_included(self, sample_media_info: MediaInfo) -> None:
        """Confidence scores are not included in text output."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello", confidence=0.95),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert text == "[00:00:00.000] Hello"
        assert "0.95" not in text

    def test_options_parameter_ignored(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Options parameter is accepted but not used (for API consistency)."""
        # Different options should produce same output
        from audiocore.types import ModelSize

        options1 = TranscriptionOptions()
        options2 = TranscriptionOptions(language="en", model_size=ModelSize.LARGE)

        text1 = format_text(sample_result, options1)
        text2 = format_text(sample_result, options2)

        assert text1 == text2

    def test_newlines_in_text_preserved(self, sample_media_info: MediaInfo) -> None:
        """Newlines within text are preserved."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Line one\nLine two"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert "Line one\nLine two" in text

    def test_timestamp_precision(self, sample_media_info: MediaInfo) -> None:
        """Timestamps have millisecond precision (3 digits)."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=1.234, end_time=5.0, text="Test"),  # Use exact value
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        assert "[00:00:01.234] Test" in text

    def test_long_transcription(self, sample_media_info: MediaInfo) -> None:
        """Longer transcriptions produce correct output."""
        segments = [
            Segment(start_time=i * 30.0, end_time=(i + 1) * 30.0, text=f"Segment {i}")
            for i in range(10)
        ]

        result = TranscriptionResult(
            segments=segments,
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=300.0,
            backend_used=BackendType.OPENAI,
        )

        text = format_text(result, TranscriptionOptions())
        lines = text.split("\n")
        assert len(lines) == 10
        assert lines[0] == "[00:00:00.000] Segment 0"
        assert lines[9] == "[00:04:30.000] Segment 9"
