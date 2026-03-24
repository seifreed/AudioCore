"""Tests for OutputFormat enum."""

import pytest

from audiocore.types import OutputFormat


class TestOutputFormat:
    """Tests for OutputFormat enum."""

    def test_values(self) -> None:
        """Test that OutputFormat has correct values."""
        assert OutputFormat.TEXT.value == "text"
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.SRT.value == "srt"
        assert OutputFormat.VTT.value == "vtt"

    def test_str_enum_inheritance(self) -> None:
        """Test that OutputFormat inherits from str and Enum for JSON serialization."""
        assert isinstance(OutputFormat.SRT, str)
        assert OutputFormat.SRT == "srt"

    def test_parse_case_insensitive(self) -> None:
        """Test parse() method with various case formats."""
        assert OutputFormat.parse("text") == OutputFormat.TEXT
        assert OutputFormat.parse("TEXT") == OutputFormat.TEXT
        assert OutputFormat.parse("srt") == OutputFormat.SRT
        assert OutputFormat.parse("SRT") == OutputFormat.SRT
        assert OutputFormat.parse("vtt") == OutputFormat.VTT
        assert OutputFormat.parse("VTT") == OutputFormat.VTT
        assert OutputFormat.parse("json") == OutputFormat.JSON
        assert OutputFormat.parse("JSON") == OutputFormat.JSON

    def test_parse_with_extension(self) -> None:
        """Test parse() handles file extensions."""
        assert OutputFormat.parse(".srt") == OutputFormat.SRT
        assert OutputFormat.parse(".vtt") == OutputFormat.VTT
        assert OutputFormat.parse(".json") == OutputFormat.JSON
        assert OutputFormat.parse(".txt") == OutputFormat.TEXT
        assert OutputFormat.parse("txt") == OutputFormat.TEXT

    def test_parse_with_spaces(self) -> None:
        """Test parse() handles values with spaces."""
        assert OutputFormat.parse(" srt ") == OutputFormat.SRT
        assert OutputFormat.parse(" .vtt ") == OutputFormat.VTT

    def test_parse_invalid_value(self) -> None:
        """Test parse() raises ValueError for invalid values."""
        with pytest.raises(ValueError) as exc_info:
            OutputFormat.parse("mp4")

        assert "Invalid output format" in str(exc_info.value)
        assert "text" in str(exc_info.value)
        assert "json" in str(exc_info.value)
        assert "srt" in str(exc_info.value)
        assert "vtt" in str(exc_info.value)

    def test_all_values_exist(self) -> None:
        """Test that all expected values exist."""
        values = [m.value for m in OutputFormat]
        assert "text" in values
        assert "json" in values
        assert "srt" in values
        assert "vtt" in values
