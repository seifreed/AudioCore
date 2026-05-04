"""Unit tests for SRT output formatter."""

import pytest

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult
from audiocore.output.srt import _format_srt_timestamp, format_srt
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


class TestFormatSrtTimestamp:
    """Tests for _format_srt_timestamp helper function."""

    def test_zero_seconds(self) -> None:
        """Zero seconds formats as 00:00:00,000."""
        result = _format_srt_timestamp(0.0)
        assert result == "00:00:00,000"

    def test_seconds_only(self) -> None:
        """Seconds less than 60 format correctly."""
        result = _format_srt_timestamp(45.0)
        assert result == "00:00:45,000"

    def test_fractional_seconds(self) -> None:
        """Fractional seconds format correctly."""
        result = _format_srt_timestamp(5.5)
        assert result == "00:00:05,500"

    def test_milliseconds_precision(self) -> None:
        """Milliseconds have 3 digits."""
        result = _format_srt_timestamp(1.123)
        assert result == "00:00:01,123"

    def test_minutes_and_seconds(self) -> None:
        """Minutes format correctly."""
        result = _format_srt_timestamp(125.0)  # 2:05.000
        assert result == "00:02:05,000"

    def test_hours_minutes_seconds(self) -> None:
        """Hours format correctly."""
        result = _format_srt_timestamp(3725.456)  # 1:02:05.456
        assert result == "01:02:05,456"

    def test_large_hours(self) -> None:
        """Large hour values format correctly."""
        result = _format_srt_timestamp(7325.500)  # 2h 2m 5.500s
        assert result == "02:02:05,500"

    def test_milliseconds_rounding(self) -> None:
        """Milliseconds are rounded using round(), not truncated."""
        result = _format_srt_timestamp(5.123)
        assert result == "00:00:05,123"

    def test_comma_separator(self) -> None:
        """SRT uses comma as milliseconds separator."""
        result = _format_srt_timestamp(1.234)
        assert "," in result
        assert "." not in result.split(":")[-1]  # No dot in last part (SS,mmm)


class TestFormatSrt:
    """Tests for format_srt function."""

    def test_multiple_segments(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Multiple segments produce correct SRT output."""
        srt = format_srt(sample_result, sample_options)

        # Should have 3 cues (blocks)
        cues = srt.strip().split("\n\n")
        assert len(cues) == 3

        # First cue
        lines1 = cues[0].split("\n")
        assert lines1[0] == "1"
        assert lines1[1] == "00:00:00,000 --> 00:00:05,234"
        assert lines1[2] == "Hello world"

        # Second cue
        lines2 = cues[1].split("\n")
        assert lines2[0] == "2"
        assert lines2[1] == "00:00:05,500 --> 00:00:10,000"
        assert lines2[2] == "How are you?"

        # Third cue
        lines3 = cues[2].split("\n")
        assert lines3[0] == "3"
        assert lines3[1] == "00:00:10,500 --> 00:00:15,750"
        assert lines3[2] == "I'm doing great"

    def test_single_segment(self, sample_media_info: MediaInfo) -> None:
        """Single segment produces one cue."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        assert srt.strip() == "1\n00:00:00,000 --> 00:00:05,000\nHello"

    def test_empty_segments(self, sample_media_info: MediaInfo) -> None:
        """Empty segments list produces empty string."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        assert srt == ""

    def test_empty_text_in_segment(self, sample_media_info: MediaInfo) -> None:
        """Segment with empty text produces valid SRT cue (2 lines: number + timestamp)."""
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

        srt = format_srt(result, TranscriptionOptions())

        # Valid SRT format with empty text: number, timestamp (no text line)
        # This is acceptable - players will show nothing for that time range
        assert "1\n00:00:00,000 --> 00:00:05,000" in srt
        assert "2\n00:00:05,000 --> 00:00:10,000\nHello" in srt

    def test_sequential_numbering(self, sample_media_info: MediaInfo) -> None:
        """Cues are numbered sequentially starting from 1."""
        segments = [
            Segment(start_time=i * 5.0, end_time=(i + 1) * 5.0, text=f"Segment {i}")
            for i in range(5)
        ]

        result = TranscriptionResult(
            segments=segments,
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=25.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        cues = srt.strip().split("\n\n")

        for i, cue in enumerate(cues, start=1):
            assert cue.startswith(f"{i}\n")

    def test_special_characters(self, sample_media_info: MediaInfo) -> None:
        """Special characters are preserved in output."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello, world! émojis: 🎉"),
                Segment(start_time=5.0, end_time=10.0, text="Quotes: \"test\" and 'single'"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        assert "Hello, world! émojis: 🎉" in srt
        assert "Quotes: \"test\" and 'single'" in srt

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

        srt = format_srt(result, TranscriptionOptions())
        assert "こんにちは世界" in srt
        assert "Привет мир" in srt
        assert "مرحبا بالعالم" in srt

    def test_multiline_text_in_segment(self, sample_media_info: MediaInfo) -> None:
        """Multiline text in segment is preserved."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=10.0, text="Line one\nLine two"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        assert "Line one\nLine two" in srt

    def test_confidence_not_included(
        self, sample_media_info: MediaInfo, sample_options: TranscriptionOptions
    ) -> None:
        """Confidence scores are not included in SRT output."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello", confidence=0.95),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, sample_options)
        assert "0.95" not in srt
        assert "confidence" not in srt.lower()

    def test_options_parameter_ignored(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Options parameter is accepted but not used (for API consistency)."""
        from audiocore.types import ModelSize

        options1 = TranscriptionOptions()
        options2 = TranscriptionOptions(language="en", model_size=ModelSize.LARGE)

        srt1 = format_srt(sample_result, options1)
        srt2 = format_srt(sample_result, options2)

        assert srt1 == srt2

    def test_trailing_newline(self, sample_media_info: MediaInfo) -> None:
        """SRT output has trailing newline for proper format."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        assert srt.endswith("\n")

    def test_hours_rollover(self, sample_media_info: MediaInfo) -> None:
        """Hours rollover correctly for long videos."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=3600.0, end_time=3610.0, text="One hour in"),
                Segment(start_time=7325.500, end_time=7335.750, text="Two hours plus"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=7340.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())
        assert "01:00:00,000 --> 01:00:10,000" in srt
        assert "02:02:05,500 --> 02:02:15,750" in srt

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

        srt = format_srt(result, TranscriptionOptions())
        cues = srt.strip().split("\n\n")

        assert len(cues) == 10
        assert cues[0].startswith("1\n")
        assert cues[9].startswith("10\n")

    def test_timestamp_format_with_comma(self, sample_media_info: MediaInfo) -> None:
        """Timestamp uses comma for milliseconds (SRT standard)."""
        result = TranscriptionResult(
            segments=[
                # Use exact float values that don't have precision issues
                Segment(start_time=1.125, end_time=5.500, text="Test"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=6.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())

        # SRT format uses comma for milliseconds
        assert "00:00:01,125" in srt
        assert "00:00:05,500" in srt
        assert "-->" in srt

    def test_cue_separator(self, sample_media_info: MediaInfo) -> None:
        """Cues are separated by blank line (double newline)."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="First"),
                Segment(start_time=5.0, end_time=10.0, text="Second"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )

        srt = format_srt(result, TranscriptionOptions())

        # Two consecutive newlines separate cues
        assert "\n\n" in srt

        cues = srt.strip().split("\n\n")
        assert len(cues) == 2


class TestSrtTimestampPrecision:
    """Regression tests for timestamp formatting precision.

    Ensures that millisecond values are correctly rounded using round()
    rather than truncated, preventing floating-point artifacts.
    """

    def test_milliseconds_rounded_not_truncated(self) -> None:
        """Regression: milliseconds should use round() not int() truncation.

        Values like 0.999 * 1000 = 999.0 should produce 999, not 998
        (which would happen with int() due to float representation).
        """
        # 1.999 seconds: (1.999 % 1) * 1000 = 999.0, should round to 999
        result = _format_srt_timestamp(1.999)
        assert result == "00:00:01,999"

    def test_millisecond_rounding_carries_to_second(self) -> None:
        """Regression: 59.9999 seconds should round correctly.

        round(0.9999 * 1000) = 1000, which carries to the next second.
        The result must be 00:01:00,000, not 00:00:59,1000 (invalid SRT).
        """
        result = _format_srt_timestamp(59.9999)
        # The total-milliseconds approach correctly carries 1000ms to 1 second
        assert result == "00:01:00,000"

    def test_exact_millisecond_values(self) -> None:
        """Exact millisecond values should format without precision loss."""
        # 5.5 seconds = 500ms
        assert _format_srt_timestamp(5.5) == "00:00:05,500"
        # 5.234 seconds = 234ms
        assert _format_srt_timestamp(5.234) == "00:00:05,234"
        # 5.001 seconds = 1ms
        assert _format_srt_timestamp(5.001) == "00:00:05,001"

    def test_zero_milliseconds_format(self) -> None:
        """Zero milliseconds should produce ,000."""
        assert _format_srt_timestamp(5.0) == "00:00:05,000"
        assert _format_srt_timestamp(0.0) == "00:00:00,000"
