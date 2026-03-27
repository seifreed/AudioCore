"""Unit tests for JSON output formatter."""

import json

import pytest

from audiocore.models.media import MediaInfo
from audiocore.models.segment import Segment
from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult
from audiocore.output.json import format_json, _prepare_for_json, _serialize_value
from audiocore.types import BackendType, ModelSize, OutputFormat


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


class TestSerializeValue:
    """Tests for _serialize_value helper function."""

    def test_enum_serialization(self) -> None:
        """Enum types are converted to their value."""
        result = _serialize_value(BackendType.OPENAI)
        assert result == "openai"

        result = _serialize_value(OutputFormat.JSON)
        assert result == "json"

        result = _serialize_value(ModelSize.LARGE)
        assert result == "large"

    def test_path_serialization(self) -> None:
        """Path objects are converted to strings."""
        from pathlib import Path

        result = _serialize_value(Path("/tmp/test.txt"))
        assert result == "/tmp/test.txt"

    def test_string_passthrough(self) -> None:
        """Strings pass through unchanged."""
        result = _serialize_value("hello")
        assert result == "hello"

    def test_int_passthrough(self) -> None:
        """Integers pass through unchanged."""
        result = _serialize_value(42)
        assert result == 42

    def test_float_passthrough(self) -> None:
        """Regular floats pass through unchanged."""
        result = _serialize_value(3.14159)
        assert result == 3.14159

    def test_float_infinity(self) -> None:
        """Float infinity is converted to None."""
        result = _serialize_value(float("inf"))
        assert result is None

        result = _serialize_value(float("-inf"))
        assert result is None

    def test_float_nan(self) -> None:
        """Float NaN is converted to None."""
        result = _serialize_value(float("nan"))
        assert result is None


class TestPrepareForJson:
    """Tests for _prepare_for_json function."""

    def test_basic_structure(self, sample_result: TranscriptionResult) -> None:
        """Prepared data has all required fields."""
        data = _prepare_for_json(sample_result)

        assert "segments" in data
        assert "media_info" in data
        assert "config_used" in data
        assert "processing_time_seconds" in data
        assert "backend_used" in data

    def test_segments_serialization(self, sample_result: TranscriptionResult) -> None:
        """Segments are serialized correctly."""
        data = _prepare_for_json(sample_result)

        assert isinstance(data["segments"], list)
        assert len(data["segments"]) == 3
        assert data["segments"][0]["text"] == "Hello world"
        assert data["segments"][0]["start_time"] == 0.0
        assert data["segments"][0]["end_time"] == 5.234

    def test_backend_used_serialization(self, sample_result: TranscriptionResult) -> None:
        """Backend type is serialized as string."""
        data = _prepare_for_json(sample_result)

        assert data["backend_used"] == "openai"


class TestFormatJson:
    """Tests for format_json function."""

    def test_valid_json(self, sample_result: TranscriptionResult) -> None:
        """Output is valid JSON parseable."""
        json_str = format_json(sample_result, TranscriptionOptions())

        # Should parse without error
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_full_structure(self, sample_result: TranscriptionResult) -> None:
        """Full result structure is present."""
        json_str = format_json(sample_result, TranscriptionOptions())
        data = json.loads(json_str)

        assert "segments" in data
        assert "media_info" in data
        assert "config_used" in data
        assert "processing_time_seconds" in data
        assert "backend_used" in data

    def test_segments_array(self, sample_media_info: MediaInfo) -> None:
        """Segments array contains all fields."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello", confidence=0.95),
                Segment(start_time=5.0, end_time=10.0, text="World", confidence=0.87),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert len(data["segments"]) == 2
        assert data["segments"][0]["start_time"] == 0.0
        assert data["segments"][0]["end_time"] == 5.0
        assert data["segments"][0]["text"] == "Hello"
        assert data["segments"][0]["confidence"] == 0.95

    def test_media_info_preserved(self, sample_media_info: MediaInfo) -> None:
        """Media info is preserved in output."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert data["media_info"]["duration"] == 120.5
        assert data["media_info"]["format"] == "mp3"
        assert data["media_info"]["sample_rate"] == 44100
        assert data["media_info"]["channels"] == 2

    def test_config_used_preserved(
        self, sample_media_info: MediaInfo, sample_options: TranscriptionOptions
    ) -> None:
        """Config options are preserved in output."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=sample_options,
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, sample_options)
        data = json.loads(json_str)

        assert data["config_used"]["language"] is None
        assert data["config_used"]["model_size"] == "base"
        assert data["config_used"]["backend"] == "auto"
        assert data["config_used"]["output_format"] == "text"

    def test_indent_parameter(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Indent parameter controls formatting."""
        # With indent
        json_indented = format_json(sample_result, sample_options, indent=2)
        assert "\n" in json_indented
        assert "  " in json_indented

        # Without indent (minified)
        json_minified = format_json(sample_result, sample_options, indent=None)
        assert "\n" not in json_minified

    def test_empty_segments(self, sample_media_info: MediaInfo) -> None:
        """Empty segments array is handled."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert data["segments"] == []

    def test_backend_type_serialization(self, sample_media_info: MediaInfo) -> None:
        """Backend type is serialized as string value."""
        for backend in [BackendType.OPENAI, BackendType.FASTER_WHISPER, BackendType.AUTO]:
            result = TranscriptionResult(
                segments=[],
                media_info=sample_media_info,
                config_used=TranscriptionOptions(),
                processing_time_seconds=0.0,
                backend_used=backend,
            )

            json_str = format_json(result, TranscriptionOptions())
            data = json.loads(json_str)

            assert data["backend_used"] == backend.value

    def test_unicode_preserved(self, sample_media_info: MediaInfo) -> None:
        """Unicode characters are preserved."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello 世界"),
                Segment(start_time=5.0, end_time=10.0, text="مرحبا"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert data["segments"][0]["text"] == "Hello 世界"
        assert data["segments"][1]["text"] == "مرحبا"

    def test_special_characters_preserved(self, sample_media_info: MediaInfo) -> None:
        """Special characters are preserved."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Quotes: \"test\" and 'single'"),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert data["segments"][0]["text"] == "Quotes: \"test\" and 'single'"

    def test_options_not_included_in_output(
        self, sample_result: TranscriptionResult, sample_options: TranscriptionOptions
    ) -> None:
        """Options parameter is accepted but not included in output structure."""
        # Options parameter is for future extensibility but not part of result
        json1 = format_json(sample_result, sample_options, indent=None)
        json2 = format_json(sample_result, TranscriptionOptions(language="es"), indent=None)

        # Both produce same output (options aren't included)
        assert json1 == json2

    def test_processing_time_seconds_preserved(self, sample_media_info: MediaInfo) -> None:
        """Processing duration is preserved."""
        result = TranscriptionResult(
            segments=[],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=42.7,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert data["processing_time_seconds"] == 42.7

    def test_round_trip_parseable(self, sample_result: TranscriptionResult) -> None:
        """JSON output can be parsed back."""
        json_str = format_json(sample_result, TranscriptionOptions())

        # Parse back
        data = json.loads(json_str)

        # Structure should be intact
        assert isinstance(data["segments"], list)
        assert len(data["segments"]) == 3
        assert data["media_info"]["duration"] == 120.5
        assert data["backend_used"] == "openai"

    def test_confidence_none_serialized(self, sample_media_info: MediaInfo) -> None:
        """Confidence None is serialized as null."""
        result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello", confidence=None),
            ],
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert data["segments"][0]["confidence"] is None

    def test_long_transcription(self, sample_media_info: MediaInfo) -> None:
        """Long transcriptions with many segments work."""
        segments = [
            Segment(start_time=i * 30.0, end_time=(i + 1) * 30.0, text=f"Segment {i}")
            for i in range(100)
        ]

        result = TranscriptionResult(
            segments=segments,
            media_info=sample_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=3000.0,
            backend_used=BackendType.OPENAI,
        )

        json_str = format_json(result, TranscriptionOptions())
        data = json.loads(json_str)

        assert len(data["segments"]) == 100
        assert data["segments"][0]["text"] == "Segment 0"
        assert data["segments"][99]["text"] == "Segment 99"
