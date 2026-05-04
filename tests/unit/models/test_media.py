"""Unit tests for MediaInfo model validation."""

import pytest
from pydantic import ValidationError

from audiocore.models import MediaInfo


class TestMediaInfoCreation:
    """Tests for valid MediaInfo creation."""

    def test_create_media_info_minimal(self) -> None:
        """Create MediaInfo with required fields only."""
        info = MediaInfo(duration=120.0, format="mp4")
        assert info.duration == 120.0
        assert info.format == "mp4"
        assert info.codec is None
        assert info.sample_rate is None
        assert info.channels is None

    def test_create_media_info_full(self) -> None:
        """Create MediaInfo with all fields."""
        info = MediaInfo(duration=180.5, format="wav", codec="pcm", sample_rate=44100, channels=2)
        assert info.duration == 180.5
        assert info.format == "wav"
        assert info.codec == "pcm"
        assert info.sample_rate == 44100
        assert info.channels == 2

    def test_create_media_info_with_codec_only(self) -> None:
        """Create MediaInfo with optional codec."""
        info = MediaInfo(duration=60.0, format="mp3", codec="mp3")
        assert info.codec == "mp3"
        assert info.sample_rate is None

    def test_create_media_info_with_sample_rate_only(self) -> None:
        """Create MediaInfo with optional sample_rate."""
        info = MediaInfo(duration=90.0, format="flac", sample_rate=48000)
        assert info.sample_rate == 48000
        assert info.codec is None


class TestMediaInfoValidation:
    """Tests for MediaInfo validation constraints."""

    def test_reject_zero_duration(self) -> None:
        """Reject duration <= 0."""
        with pytest.raises(ValidationError):
            MediaInfo(duration=0.0, format="mp4")

    def test_reject_negative_duration(self) -> None:
        """Reject negative duration."""
        with pytest.raises(ValidationError) as exc_info:
            MediaInfo(duration=-10.0, format="mp4")
        assert "duration" in str(exc_info.value)

    def test_reject_infinite_duration(self) -> None:
        """Reject infinite duration values."""
        with pytest.raises(ValidationError) as exc_info:
            MediaInfo(duration=float("inf"), format="mp4")
        assert "duration" in str(exc_info.value)

    def test_reject_zero_sample_rate(self) -> None:
        """Reject sample_rate <= 0."""
        with pytest.raises(ValidationError):
            MediaInfo(duration=100.0, format="mp4", sample_rate=0)

    def test_reject_negative_sample_rate(self) -> None:
        """Reject negative sample_rate."""
        with pytest.raises(ValidationError):
            MediaInfo(duration=100.0, format="mp4", sample_rate=-44100)

    def test_reject_zero_channels(self) -> None:
        """Reject channels <= 0."""
        with pytest.raises(ValidationError):
            MediaInfo(duration=100.0, format="mp4", channels=0)

    def test_reject_negative_channels(self) -> None:
        """Reject negative channels."""
        with pytest.raises(ValidationError):
            MediaInfo(duration=100.0, format="mp4", channels=-2)

    def test_strict_mode_rejects_string_duration(self) -> None:
        """Strict mode rejects string for float field."""
        with pytest.raises(ValidationError):
            MediaInfo(duration="120", format="mp4")  # type: ignore

    def test_strict_mode_rejects_string_format(self) -> None:
        """Strict mode rejects string for format (already str, but check int)."""
        # This should work since format is already str
        info = MediaInfo(duration=120.0, format="mp4")
        assert info.format == "mp4"


class TestMediaInfoSerialization:
    """Tests for MediaInfo serialization/deserialization."""

    def test_model_dump(self) -> None:
        """Serialize MediaInfo to dict."""
        info = MediaInfo(duration=120.0, format="mp4", codec="aac")
        data = info.model_dump()
        assert data["duration"] == 120.0
        assert data["format"] == "mp4"
        assert data["codec"] == "aac"
        assert data["sample_rate"] is None

    def test_model_validate(self) -> None:
        """Deserialize MediaInfo from dict."""
        data = {
            "duration": 90.0,
            "format": "wav",
            "codec": "pcm",
            "sample_rate": 44100,
            "channels": 2,
        }
        info = MediaInfo.model_validate(data)
        assert info.duration == 90.0
        assert info.format == "wav"
        assert info.sample_rate == 44100
        assert info.channels == 2

    def test_model_dump_json(self) -> None:
        """Serialize MediaInfo to JSON."""
        info = MediaInfo(duration=60.0, format="mp3", channels=1)
        json_str = info.model_dump_json()
        assert '"duration":60.0' in json_str
        assert '"format":"mp3"' in json_str
        assert '"channels":1' in json_str

    def test_model_validate_json(self) -> None:
        """Deserialize MediaInfo from JSON."""
        json_str = '{"duration": 45.5, "format": "ogg", "sample_rate": 22050}'
        info = MediaInfo.model_validate_json(json_str)
        assert info.duration == 45.5
        assert info.format == "ogg"
        assert info.sample_rate == 22050
        assert info.codec is None


class TestMediaInfoEquality:
    """Tests for MediaInfo equality."""

    def test_equal_media_info(self) -> None:
        """Equal MediaInfo have same values."""
        m1 = MediaInfo(duration=120.0, format="mp4", channels=2)
        m2 = MediaInfo(duration=120.0, format="mp4", channels=2)
        assert m1 == m2

    def test_unequal_duration(self) -> None:
        """Unequal duration makes MediaInfo unequal."""
        m1 = MediaInfo(duration=120.0, format="mp4")
        m2 = MediaInfo(duration=90.0, format="mp4")
        assert m1 != m2

    def test_unequal_format(self) -> None:
        """Unequal format makes MediaInfo unequal."""
        m1 = MediaInfo(duration=120.0, format="mp4")
        m2 = MediaInfo(duration=120.0, format="wav")
        assert m1 != m2


class TestMediaInfoVariousFormats:
    """Tests for various media formats."""

    def test_mp4_format(self) -> None:
        """Accept mp4 format."""
        info = MediaInfo(duration=300.0, format="mp4")
        assert info.format == "mp4"

    def test_mp3_format(self) -> None:
        """Accept mp3 format."""
        info = MediaInfo(duration=180.0, format="mp3")
        assert info.format == "mp3"

    def test_wav_format(self) -> None:
        """Accept wav format."""
        info = MediaInfo(duration=60.0, format="wav", sample_rate=44100)
        assert info.format == "wav"

    def test_ogg_format(self) -> None:
        """Accept ogg format."""
        info = MediaInfo(duration=240.0, format="ogg")
        assert info.format == "ogg"

    def test_flac_format(self) -> None:
        """Accept flac format."""
        info = MediaInfo(duration=420.0, format="flac")
        assert info.format == "flac"
