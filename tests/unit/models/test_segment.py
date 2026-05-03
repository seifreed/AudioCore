"""Unit tests for Segment model validation."""

import pytest
from pydantic import ValidationError

from audiocore.models import Segment


class TestSegmentCreation:
    """Tests for valid Segment creation."""

    def test_create_segment_minimal(self) -> None:
        """Create segment with required fields only."""
        segment = Segment(start_time=0.0, end_time=5.0, text="Hello world")
        assert segment.start_time == 0.0
        assert segment.end_time == 5.0
        assert segment.text == "Hello world"
        assert segment.confidence is None

    def test_create_segment_full(self) -> None:
        """Create segment with all fields."""
        segment = Segment(start_time=1.5, end_time=10.25, text="Transcribed text", confidence=0.95)
        assert segment.start_time == 1.5
        assert segment.end_time == 10.25
        assert segment.text == "Transcribed text"
        assert segment.confidence == 0.95

    def test_create_segment_confidence_zero(self) -> None:
        """Create segment with confidence at boundary."""
        segment = Segment(start_time=0.0, end_time=1.0, text="test", confidence=0.0)
        assert segment.confidence == 0.0

    def test_create_segment_confidence_one(self) -> None:
        """Create segment with confidence at upper boundary."""
        segment = Segment(start_time=0.0, end_time=1.0, text="test", confidence=1.0)
        assert segment.confidence == 1.0


class TestSegmentValidation:
    """Tests for Segment validation constraints."""

    def test_reject_negative_start_time(self) -> None:
        """Reject negative start_time."""
        with pytest.raises(ValidationError) as exc_info:
            Segment(start_time=-1.0, end_time=5.0, text="test")
        assert "start_time" in str(exc_info.value)

    def test_reject_negative_end_time(self) -> None:
        """Reject negative end_time."""
        with pytest.raises(ValidationError) as exc_info:
            Segment(start_time=0.0, end_time=-5.0, text="test")
        assert "end_time" in str(exc_info.value)

    def test_reject_end_time_less_than_start_time(self) -> None:
        """Reject end_time < start_time."""
        with pytest.raises(ValidationError) as exc_info:
            Segment(start_time=10.0, end_time=5.0, text="test")
        assert "end_time" in str(exc_info.value).lower()

    def test_accepts_empty_text(self) -> None:
        """Accept empty text (valid before transcription)."""
        segment = Segment(start_time=0.0, end_time=5.0, text="")
        assert segment.text == ""

    def test_reject_confidence_above_one(self) -> None:
        """Reject confidence > 1."""
        with pytest.raises(ValidationError):
            Segment(start_time=0.0, end_time=5.0, text="test", confidence=1.5)

    def test_reject_confidence_below_zero(self) -> None:
        """Reject confidence < 0."""
        with pytest.raises(ValidationError):
            Segment(start_time=0.0, end_time=5.0, text="test", confidence=-0.1)

    def test_strict_mode_rejects_string_start_time(self) -> None:
        """Strict mode rejects string for float field."""
        with pytest.raises(ValidationError):
            Segment(start_time="0", end_time=5.0, text="test")  # type: ignore

    def test_strict_mode_rejects_string_end_time(self) -> None:
        """Strict mode rejects string for float field."""
        with pytest.raises(ValidationError):
            Segment(start_time=0.0, end_time="5", text="test")  # type: ignore


    def test_reject_infinite_start_time(self) -> None:
        """Regression: float('inf') must be rejected for start_time."""
        with pytest.raises(ValidationError, match="must be finite"):
            Segment(start_time=float("inf"), end_time=5.0, text="test")

    def test_reject_infinite_end_time(self) -> None:
        """Regression: float('inf') must be rejected for end_time."""
        with pytest.raises(ValidationError, match="must be finite"):
            Segment(start_time=0.0, end_time=float("inf"), text="test")

    def test_reject_nan_start_time(self) -> None:
        """Regression: float('nan') must be rejected for start_time."""
        with pytest.raises(ValidationError, match="must be finite"):
            Segment(start_time=float("nan"), end_time=5.0, text="test")


class TestSegmentSerialization:
    """Tests for Segment serialization/deserialization."""

    def test_model_dump(self) -> None:
        """Serialize segment to dict."""
        segment = Segment(start_time=0.0, end_time=5.5, text="Hello", confidence=0.9)
        data = segment.model_dump()
        assert data["start_time"] == 0.0
        assert data["end_time"] == 5.5
        assert data["text"] == "Hello"
        assert data["confidence"] == 0.9

    def test_model_validate(self) -> None:
        """Deserialize segment from dict."""
        data = {"start_time": 1.0, "end_time": 10.0, "text": "World", "confidence": None}
        segment = Segment.model_validate(data)
        assert segment.start_time == 1.0
        assert segment.end_time == 10.0
        assert segment.text == "World"
        assert segment.confidence is None

    def test_model_dump_json(self) -> None:
        """Serialize segment to JSON."""
        segment = Segment(start_time=0.0, end_time=5.0, text="test", confidence=0.75)
        json_str = segment.model_dump_json()
        assert '"start_time":0.0' in json_str
        assert '"confidence":0.75' in json_str

    def test_model_validate_json(self) -> None:
        """Deserialize segment from JSON."""
        json_str = '{"start_time": 0.0, "end_time": 3.5, "text": "JSON test", "confidence": null}'
        segment = Segment.model_validate_json(json_str)
        assert segment.start_time == 0.0
        assert segment.end_time == 3.5
        assert segment.text == "JSON test"
        assert segment.confidence is None


class TestSegmentEquality:
    """Tests for Segment equality."""

    def test_equal_segments(self) -> None:
        """Equal segments have same values."""
        s1 = Segment(start_time=0.0, end_time=5.0, text="test", confidence=0.9)
        s2 = Segment(start_time=0.0, end_time=5.0, text="test", confidence=0.9)
        assert s1 == s2

    def test_unequal_start_time(self) -> None:
        """Unequal start_time makes segments unequal."""
        s1 = Segment(start_time=0.0, end_time=5.0, text="test")
        s2 = Segment(start_time=1.0, end_time=5.0, text="test")
        assert s1 != s2

    def test_unequal_text(self) -> None:
        """Unequal text makes segments unequal."""
        s1 = Segment(start_time=0.0, end_time=5.0, text="test1")
        s2 = Segment(start_time=0.0, end_time=5.0, text="test2")
        assert s1 != s2
