"""Unit tests for TranscriptionOptions and TranscriptionResult models."""

import pytest
from pydantic import ValidationError

from audiocore.models import (
    FailedSegment,
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
)
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class TestTranscriptionOptionsDefaults:
    """Tests for TranscriptionOptions default values."""

    def test_default_backend(self) -> None:
        """Backend defaults to AUTO."""
        opts = TranscriptionOptions()
        assert opts.backend == BackendType.AUTO

    def test_default_model_size(self) -> None:
        """Model size defaults to BASE."""
        opts = TranscriptionOptions()
        assert opts.model_size == ModelSize.BASE

    def test_default_output_format(self) -> None:
        """Output format defaults to TEXT."""
        opts = TranscriptionOptions()
        assert opts.output_format == OutputFormat.TEXT

    def test_default_backend_preference(self) -> None:
        """Backend preference defaults to AUTO."""
        opts = TranscriptionOptions()
        assert opts.backend_preference == SelectionPolicy.AUTO

    def test_default_language_is_none(self) -> None:
        """Language defaults to None."""
        opts = TranscriptionOptions()
        assert opts.language is None


class TestTranscriptionOptionsCustomValues:
    """Tests for TranscriptionOptions with custom values."""

    def test_custom_backend_openai(self) -> None:
        """Accept OPENAI backend."""
        opts = TranscriptionOptions(backend=BackendType.OPENAI)
        assert opts.backend == BackendType.OPENAI

    def test_custom_backend_faster_whisper(self) -> None:
        """Accept FASTER_WHISPER backend."""
        opts = TranscriptionOptions(backend=BackendType.FASTER_WHISPER)
        assert opts.backend == BackendType.FASTER_WHISPER

    def test_custom_model_size(self) -> None:
        """Accept all model sizes."""
        for size in [
            ModelSize.TINY,
            ModelSize.BASE,
            ModelSize.SMALL,
            ModelSize.MEDIUM,
            ModelSize.LARGE,
        ]:
            opts = TranscriptionOptions(model_size=size)
            assert opts.model_size == size

    def test_custom_output_format(self) -> None:
        """Accept all output formats."""
        for fmt in [OutputFormat.TEXT, OutputFormat.SRT, OutputFormat.VTT, OutputFormat.JSON]:
            opts = TranscriptionOptions(output_format=fmt)
            assert opts.output_format == fmt

    def test_custom_backend_preference(self) -> None:
        """Accept all backend preferences."""
        for policy in [
            SelectionPolicy.AUTO,
            SelectionPolicy.PREFER_LOCAL,
            SelectionPolicy.PREFER_CLOUD,
        ]:
            opts = TranscriptionOptions(backend_preference=policy)
            assert opts.backend_preference == policy

    def test_custom_language(self) -> None:
        """Accept language code."""
        opts = TranscriptionOptions(language="en")
        assert opts.language == "en"

    def test_all_custom_values(self) -> None:
        """Accept all custom values together."""
        opts = TranscriptionOptions(
            language="es",
            model_size=ModelSize.LARGE,
            backend=BackendType.OPENAI,
            output_format=OutputFormat.SRT,
            backend_preference=SelectionPolicy.PREFER_CLOUD,
        )
        assert opts.language == "es"
        assert opts.model_size == ModelSize.LARGE
        assert opts.backend == BackendType.OPENAI
        assert opts.output_format == OutputFormat.SRT
        assert opts.backend_preference == SelectionPolicy.PREFER_CLOUD


class TestTranscriptionOptionsStrictMode:
    """Tests for TranscriptionOptions strict validation."""

    def test_strict_mode_rejects_string_for_model_size(self) -> None:
        """Strict mode requires ModelSize enum."""
        with pytest.raises(ValidationError):
            TranscriptionOptions(model_size="base")  # type: ignore

    def test_strict_mode_rejects_invalid_backend(self) -> None:
        """Strict mode rejects invalid backend value."""
        with pytest.raises(ValidationError):
            TranscriptionOptions(backend="invalid")  # type: ignore


class TestTranscriptionOptionsSerialization:
    """Tests for TranscriptionOptions serialization/deserialization."""

    def test_model_dump(self) -> None:
        """Serialize TranscriptionOptions to dict."""
        opts = TranscriptionOptions(language="fr", model_size=ModelSize.SMALL)
        data = opts.model_dump()
        assert data["language"] == "fr"
        assert data["model_size"] == ModelSize.SMALL
        assert data["backend"] == BackendType.AUTO

    def test_model_validate(self) -> None:
        """Deserialize TranscriptionOptions from dict."""
        # Note: With strict=True mode, model_validate requires actual enum instances
        # for enum fields, not strings. Use model_validate_json for string values.
        data = {
            "language": "de",
            "model_size": ModelSize.MEDIUM,
            "backend": BackendType.OPENAI,
            "output_format": OutputFormat.JSON,
            "backend_preference": SelectionPolicy.PREFER_LOCAL,
        }
        opts = TranscriptionOptions.model_validate(data)
        assert opts.language == "de"
        assert opts.model_size == ModelSize.MEDIUM
        assert opts.backend == BackendType.OPENAI
        assert opts.output_format == OutputFormat.JSON
        assert opts.backend_preference == SelectionPolicy.PREFER_LOCAL

    def test_model_dump_json(self) -> None:
        """Serialize TranscriptionOptions to JSON."""
        opts = TranscriptionOptions(language="en", backend=BackendType.OPENAI)
        json_str = opts.model_dump_json()
        assert '"language":"en"' in json_str
        assert '"backend":"openai"' in json_str

    def test_model_validate_json(self) -> None:
        """Deserialize TranscriptionOptions from JSON."""
        json_str = '{"language": "ja", "model_size": "large"}'
        opts = TranscriptionOptions.model_validate_json(json_str)
        assert opts.language == "ja"
        assert opts.model_size == ModelSize.LARGE


class TestTranscriptionResultCreation:
    """Tests for valid TranscriptionResult creation."""

    def test_create_result_minimal(self) -> None:
        """Create TranscriptionResult with required fields."""
        result = TranscriptionResult(
            segments=[],
            media_info=MediaInfo(duration=120.0, format="mp4"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=15.5,
            backend_used=BackendType.OPENAI,
        )
        assert len(result.segments) == 0
        assert result.processing_time_seconds == 15.5
        assert result.backend_used == BackendType.OPENAI

    def test_create_result_with_segments(self) -> None:
        """Create TranscriptionResult with segments."""
        segments = [
            Segment(start_time=0.0, end_time=5.0, text="Hello"),
            Segment(start_time=5.0, end_time=10.0, text="world"),
        ]
        result = TranscriptionResult(
            segments=segments,
            media_info=MediaInfo(duration=60.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.FASTER_WHISPER,
        )
        assert len(result.segments) == 2
        assert result.segments[0].text == "Hello"
        assert result.segments[1].text == "world"

    def test_create_result_with_all_options(self) -> None:
        """Create TranscriptionResult with full config options."""
        config = TranscriptionOptions(
            language="en",
            model_size=ModelSize.LARGE,
            backend=BackendType.OPENAI,
            output_format=OutputFormat.SRT,
            backend_preference=SelectionPolicy.PREFER_LOCAL,
        )
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
            media_info=MediaInfo(duration=30.0, format="mp3"),
            config_used=config,
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )
        assert result.config_used.language == "en"
        assert result.config_used.model_size == ModelSize.LARGE


class TestTranscriptionResultValidation:
    """Tests for TranscriptionResult validation constraints."""

    def test_reject_negative_processing_time(self) -> None:
        """Reject negative processing_time_seconds."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                segments=[],
                media_info=MediaInfo(duration=10.0, format="mp4"),
                config_used=TranscriptionOptions(),
                processing_time_seconds=-5.0,
                backend_used=BackendType.OPENAI,
            )

    def test_reject_infinite_processing_time(self) -> None:
        """Reject infinite processing_time_seconds."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                segments=[],
                media_info=MediaInfo(duration=10.0, format="mp4"),
                config_used=TranscriptionOptions(),
                processing_time_seconds=float("inf"),
                backend_used=BackendType.OPENAI,
            )

    def test_accept_zero_duration(self) -> None:
        """Accept zero duration_seconds."""
        result = TranscriptionResult(
            segments=[],
            media_info=MediaInfo(duration=10.0, format="mp4"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.0,
            backend_used=BackendType.OPENAI,
        )
        assert result.processing_time_seconds == 0.0

    def test_strict_mode_rejects_string_duration(self) -> None:
        """Strict mode rejects string for duration_seconds."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                segments=[],
                media_info=MediaInfo(duration=10.0, format="mp4"),
                config_used=TranscriptionOptions(),
                processing_time_seconds="5.0",  # type: ignore
                backend_used=BackendType.OPENAI,
            )

    def test_reject_invalid_failed_segment_times(self) -> None:
        """Reject invalid failed segment timing metadata."""
        with pytest.raises(ValidationError):
            FailedSegment(start_time=float("inf"), end_time=10.0, error="timeout")

        with pytest.raises(ValidationError):
            FailedSegment(start_time=10.0, end_time=5.0, error="timeout")

    def test_validate_nested_segments(self) -> None:
        """Validate nested segment models."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                segments=[Segment(start_time=10.0, end_time=5.0, text="invalid")],  # end < start
                media_info=MediaInfo(duration=10.0, format="mp4"),
                config_used=TranscriptionOptions(),
                processing_time_seconds=5.0,
                backend_used=BackendType.OPENAI,
            )


class TestTranscriptionResultSerialization:
    """Tests for TranscriptionResult serialization/deserialization."""

    def test_model_dump(self) -> None:
        """Serialize TranscriptionResult to dict."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
            media_info=MediaInfo(duration=60.0, format="mp4"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=10.0,
            backend_used=BackendType.OPENAI,
        )
        data = result.model_dump()
        assert len(data["segments"]) == 1
        assert data["processing_time_seconds"] == 10.0
        assert data["backend_used"] == BackendType.OPENAI

    def test_model_validate(self) -> None:
        """Deserialize TranscriptionResult from dict."""
        # Note: With strict=True mode, model_validate requires actual enum instances
        # for enum fields, not strings. Use model_validate_json for string values.
        data = {
            "segments": [{"start_time": 0.0, "end_time": 3.5, "text": "Hello", "confidence": None}],
            "media_info": {
                "duration": 120.0,
                "format": "wav",
                "codec": None,
                "sample_rate": None,
                "channels": None,
            },
            "config_used": {
                "language": None,
                "model_size": ModelSize.BASE,
                "backend": BackendType.AUTO,
                "output_format": OutputFormat.TEXT,
                "backend_preference": SelectionPolicy.AUTO,
            },
            "processing_time_seconds": 5.5,
            "backend_used": BackendType.OPENAI,
        }
        result = TranscriptionResult.model_validate(data)
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hello"
        assert result.backend_used == BackendType.OPENAI

    def test_model_dump_json(self) -> None:
        """Serialize TranscriptionResult to JSON."""
        result = TranscriptionResult(
            segments=[],
            media_info=MediaInfo(duration=30.0, format="mp3"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=2.0,
            backend_used=BackendType.FASTER_WHISPER,
        )
        json_str = result.model_dump_json()
        assert '"backend_used":"faster_whisper"' in json_str

    def test_model_validate_json(self) -> None:
        """Deserialize TranscriptionResult from JSON."""
        json_str = """{
            "segments": [{"start_time": 0.0, "end_time": 5.0, "text": "test", "confidence": null}],
            "media_info": {"duration": 10.0, "format": "mp4", "codec": null, "sample_rate": null, "channels": null},
            "config_used": {"language": null, "model_size": "base", "backend": "auto", "output_format": "text", "backend_preference": "auto"},
            "processing_time_seconds": 3.5,
            "backend_used": "faster_whisper"
        }"""
        result = TranscriptionResult.model_validate_json(json_str)
        assert len(result.segments) == 1
        assert result.segments[0].text == "test"
        assert result.backend_used == BackendType.FASTER_WHISPER


class TestTranscriptionResultEquality:
    """Tests for TranscriptionResult equality."""

    def test_equal_results(self) -> None:
        """Equal results have same values."""
        r1 = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
            media_info=MediaInfo(duration=10.0, format="mp4"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )
        r2 = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
            media_info=MediaInfo(duration=10.0, format="mp4"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )
        assert r1 == r2
