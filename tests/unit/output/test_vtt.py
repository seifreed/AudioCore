"""Unit tests for VTT output formatter."""

import pytest

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult
from audiocore.output.vtt import _format_vtt_timestamp, format_vtt
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


class TestFormatVttTimestamp:
    """Tests for _format_vtt_timestamp helper function."""

    def test_zero_seconds(self) -> None:
        """Zero seconds formats as 00:00:00.000."""
        result = _format_vtt_timestamp(0.0)
        assert result == "00:00:00.000"

    def test_seconds_only(self) -> None:
        """Seconds less than 60 format correctly."""
        result = _format_vtt_timestamp(45.0)
        assert result == "00:00:45.000"

    def test_fractional_seconds(self) -> None:
        """Fractional seconds format correctly."""
        result = _format_vtt_timestamp(5.5)
        assert result == "00:00:05.500"

    def test_milliseconds_precision(self) -> None:
        """Milliseconds have 3 digits."""
        result = _format_vtt_timestamp(1.123)
        assert result == "00:00:01.123"

    def test_minutes_and_seconds(self) -> None:
        """Minutes format correctly."""
        result = _format_vtt_timestamp(125.0)  # 2:05.000
        assert result == "00:02:05.000"

    def test_hours_minutes_seconds(self) -> None:
        """Hours format correctly."""
        result = _format_vtt_timestamp(3725.456)  # 1:02:05.456
        assert result == "01:02:05.456"

    def test_large_hours(self) -> None:
        """Large hour values format correctly."""
        result = _format_vtt_timestamp(7325.500)  # 2h 2m 5.500s
        assert result == "02:02:05.500"

    def test_milliseconds_truncation(self) -> None:
        """Milliseconds are truncated, not rounded."""
        result = _format_vtt_timestamp(5.123)
        assert result == "00:00:05.123"

    def test_period_separator(self) -> None:
        """VTT uses period as milliseconds separator."""
        result = _format_vtt_timestamp(1.234)
        assert "." in result
        assert "," not in result.split(":")[-1]  # No comma in last part (SS.mmm)

    def test_timestamp_overflow_carries_to_second(self) -> None:
        """Regression: 59.9999s must not produce .1000 (invalid VTT).

        The result must be 00:01:00.000, not 00:00:59.1000.
        """
        result = _format_vtt_timestamp(59.9999)
        assert result == "00:01:00.000"


class TestFormatVtt:
    """Tests for format_vtt function."""

    def test_webvtt_header(self, sample_media_info: MediaInfo) -> None:
        """Output starts with WEBVTT header."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, TranscriptionOptions())
        assert vtt.startswith("WEBVTT\n")

    def test_webvtt_header_only_empty_segments(self, sample_media_info: MediaInfo) -> None:
        """Empty segments list produces WEBVTT header only."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, TranscriptionOptions())
        assert vtt == "WEBVTT\n\n"

    def test_multiple_segments(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Multiple segments produce correct VTT output."""
        vtt = format_vtt(sample_result, sample_options)

        # Should start with WEBVTT and have blank line before cues
        assert vtt.startswith("WEBVTT\n\n")

        # Split into cue blocks
        lines = vtt.strip().split("\n\n")
        assert lines[0] == "WEBVTT"  # First element is header

        # Cue blocks start after header
        cues = lines[1:]

        # First cue
        assert "00:00:00.000 --> 00:00:05.234" in cues[0]
        assert "Hello world" in cues[0]

        # Second cue
        assert "00:00:05.500 --> 00:00:10.000" in cues[1]
        assert "How are you?" in cues[1]

        # Third cue
        assert "00:00:10.500 --> 00:00:15.750" in cues[2]
        assert "I'm doing great" in cues[2]

    def test_single_segment(self, sample_media_info: MediaInfo) -> None:
        """Single segment produces valid VTT."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, TranscriptionOptions())
        assert "WEBVTT" in vtt
        assert "00:00:00.000 --> 00:00:05.000" in vtt
        assert "Hello" in vtt

    def test_no_sequential_numbering(self, sample_media_info: MediaInfo) -> None:
        """VTT does NOT have sequential numbering (unlike SRT)."""
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

        vtt = format_vtt(result, TranscriptionOptions())

        # VTT should NOT have numbered cues (no "1\n", "2\n", etc.)
        lines = vtt.strip().split("\n")
        # Check that timestamps don't follow numbers
        for line in lines:
            # VTT cues start with timestamps, not numbers
            if "-->" in line:
                assert line.startswith("00:") or line.startswith("01:") or line.startswith("02:")

    def test_empty_text_in_segment(self, sample_media_info: MediaInfo) -> None:
        """Segment with empty text produces cue without text line."""
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

        vtt = format_vtt(result, TranscriptionOptions())

        # Should have WEBVTT header and valid cue format
        assert vtt.startswith("WEBVTT\n\n")
        assert "00:00:00.000 --> 00:00:05.000" in vtt
        assert "Hello" in vtt

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

        vtt = format_vtt(result, TranscriptionOptions())
        assert "Hello, world! émojis: 🎉" in vtt
        assert "Quotes: \"test\" and 'single'" in vtt

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

        vtt = format_vtt(result, TranscriptionOptions())
        assert "こんにちは世界" in vtt
        assert "Привет мир" in vtt
        assert "مرحبا بالعالم" in vtt

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

        vtt = format_vtt(result, TranscriptionOptions())
        assert "Line one\nLine two" in vtt

    def test_confidence_not_included(
        self, sample_media_info: MediaInfo, sample_options: TranscriptionOptions
    ) -> None:
        """Confidence scores are not included in VTT output."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello", confidence=0.95),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, sample_options)
        assert "0.95" not in vtt
        assert "confidence" not in vtt.lower()

    def test_options_parameter_ignored(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Options parameter is accepted but not used (for API consistency)."""
        from audiocore.types import ModelSize

        options1 = TranscriptionOptions()
        options2 = TranscriptionOptions(language="en", model_size=ModelSize.LARGE)

        vtt1 = format_vtt(sample_result, options1)
        vtt2 = format_vtt(sample_result, options2)

        assert vtt1 == vtt2

    def test_trailing_newline(self, sample_media_info: MediaInfo) -> None:
        """VTT output has trailing newline for proper format."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, TranscriptionOptions())
        assert vtt.endswith("\n")

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

        vtt = format_vtt(result, TranscriptionOptions())
        assert "01:00:00.000 --> 01:00:10.000" in vtt
        assert "02:02:05.500 --> 02:02:15.750" in vtt

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

        vtt = format_vtt(result, TranscriptionOptions())

        # Should have WEBVTT header and all segments
        assert vtt.startswith("WEBVTT\n\n")

        lines = vtt.strip().split("\n\n")
        # First element is WEBVTT, rest are cue blocks
        assert len(lines) == 11  # WEBVTT + 10 cues
        assert lines[0] == "WEBVTT"

    def test_timestamp_format_with_period(self, sample_media_info: MediaInfo) -> None:
        """Timestamp uses period for milliseconds (VTT standard)."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=1.125, end_time=5.500, text="Test"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=6.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, TranscriptionOptions())

        # VTT format uses period for milliseconds
        assert "00:00:01.125" in vtt
        assert "00:00:05.500" in vtt
        assert "-->" in vtt

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

        vtt = format_vtt(result, TranscriptionOptions())

        # Two consecutive newlines separate cues
        assert "\n\n" in vtt

        lines = vtt.strip().split("\n\n")
        # WEBVTT header, then cues separated by double newline
        assert len(lines) == 3  # WEBVTT + 2 cues

    def test_header_format(self, sample_media_info: MediaInfo) -> None:
        """WEBVTT header is exactly 'WEBVTT' followed by newline."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, TranscriptionOptions())

        # Header should be exactly "WEBVTT\n\n" before cue content
        assert vtt.startswith("WEBVTT\n\n")

    def test_vtt_vs_srt_timestamp_difference(
        self, sample_media_info: MediaInfo, sample_options: TranscriptionOptions
    ) -> None:
        """VTT timestamps use period, SRT uses comma."""
        from audiocore.output.srt import format_srt

        result = TranscriptionResult(
            segments=[
                Segment(start_time=1.234, end_time=5.567, text="Test"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=6.0,
            backend_used=BackendType.OPENAI,
        )

        vtt = format_vtt(result, sample_options)
        srt = format_srt(result, sample_options)

        # VTT uses period for milliseconds
        assert "." in vtt.split("--")[0]  # Period in timestamp before -->
        # SRT uses comma for milliseconds
        assert "," in srt.split("--")[0]  # Comma in timestamp before -->
