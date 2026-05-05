"""Tests for BackendType and ModelSize enums."""

import pytest

from audiocore.types import BackendType, ModelSize


class TestBackendType:
    """Tests for BackendType enum."""

    def test_values(self) -> None:
        """Test that BackendType has correct values."""
        assert BackendType.OPENAI.value == "openai"
        assert BackendType.FASTER_WHISPER.value == "faster_whisper"
        assert BackendType.AUTO.value == "auto"

    def test_str_enum_inheritance(self) -> None:
        """Test that BackendType inherits from str and Enum for JSON serialization."""
        assert isinstance(BackendType.OPENAI, str)
        assert BackendType.OPENAI == "openai"

    def test_parse_case_insensitive(self) -> None:
        """Test parse() method with various case formats."""
        assert BackendType.parse("openai") == BackendType.OPENAI
        assert BackendType.parse("OpenAI") == BackendType.OPENAI
        assert BackendType.parse("OPENAI") == BackendType.OPENAI
        assert BackendType.parse("faster-whisper") == BackendType.FASTER_WHISPER
        assert BackendType.parse("FASTER_WHISPER") == BackendType.FASTER_WHISPER
        assert BackendType.parse("Faster Whisper") == BackendType.FASTER_WHISPER
        assert BackendType.parse("auto") == BackendType.AUTO
        assert BackendType.parse("AUTO") == BackendType.AUTO

    def test_parse_strips_surrounding_whitespace(self) -> None:
        """Regression: config/CLI values with incidental whitespace should parse."""
        assert BackendType.parse(" openai ") == BackendType.OPENAI
        assert BackendType.parse("\tfaster-whisper\n") == BackendType.FASTER_WHISPER

    def test_parse_invalid_value(self) -> None:
        """Test parse() raises ValueError for invalid values."""
        with pytest.raises(ValueError) as exc_info:
            BackendType.parse("invalid_backend")

        assert "Invalid backend type" in str(exc_info.value)
        assert "openai" in str(exc_info.value)
        assert "faster_whisper" in str(exc_info.value)
        assert "auto" in str(exc_info.value)

    def test_all_values_exist(self) -> None:
        """Test that all expected values exist."""
        values = [m.value for m in BackendType]
        assert "openai" in values
        assert "faster_whisper" in values
        assert "auto" in values


class TestModelSize:
    """Tests for ModelSize enum."""

    def test_values(self) -> None:
        """Test that ModelSize has correct values."""
        assert ModelSize.TINY.value == "tiny"
        assert ModelSize.BASE.value == "base"
        assert ModelSize.SMALL.value == "small"
        assert ModelSize.MEDIUM.value == "medium"
        assert ModelSize.LARGE.value == "large"
        assert ModelSize.LARGE_V3.value == "large-v3"
        assert ModelSize.LARGE_V3_TURBO.value == "large-v3-turbo"

    def test_str_enum_inheritance(self) -> None:
        """Test that ModelSize inherits from str and Enum for JSON serialization."""
        assert isinstance(ModelSize.LARGE, str)
        assert ModelSize.LARGE == "large"

    def test_parse_case_insensitive(self) -> None:
        """Test parse() method with various case formats."""
        assert ModelSize.parse("tiny") == ModelSize.TINY
        assert ModelSize.parse("Tiny") == ModelSize.TINY
        assert ModelSize.parse("TINY") == ModelSize.TINY
        assert ModelSize.parse("large") == ModelSize.LARGE
        assert ModelSize.parse("LARGE") == ModelSize.LARGE

    def test_parse_invalid_value(self) -> None:
        """Test parse() raises ValueError for invalid values."""
        with pytest.raises(ValueError) as exc_info:
            ModelSize.parse("extra_large")

        assert "Invalid model size" in str(exc_info.value)
        assert "tiny" in str(exc_info.value)
        assert "base" in str(exc_info.value)
        assert "small" in str(exc_info.value)
        assert "medium" in str(exc_info.value)
        assert "large" in str(exc_info.value)

    def test_all_values_exist(self) -> None:
        """Test that all 7 expected values exist."""
        values = [m.value for m in ModelSize]
        assert len(values) == 7
        assert "tiny" in values
        assert "base" in values
        assert "small" in values
        assert "medium" in values
        assert "large" in values
        assert "large-v3" in values
        assert "large-v3-turbo" in values

    def test_parse_hyphenated_model_sizes(self) -> None:
        """Test parse() works for hyphenated model sizes like large-v3.

        Regression test: ModelSize.parse("large-v3") previously failed because
        the normalization replaced hyphens with underscores, but the enum
        values use hyphens (large-v3, large-v3-turbo).
        """
        assert ModelSize.parse("large-v3") == ModelSize.LARGE_V3
        assert ModelSize.parse("large-v3-turbo") == ModelSize.LARGE_V3_TURBO

    def test_parse_underscore_model_sizes(self) -> None:
        """Test parse() accepts underscores as aliases for hyphens.

        Users may type large_v3 instead of large-v3; both should work.
        """
        assert ModelSize.parse("large_v3") == ModelSize.LARGE_V3
        assert ModelSize.parse("large_v3_turbo") == ModelSize.LARGE_V3_TURBO

    def test_parse_camelcase_with_digit_uppercase_boundary(self) -> None:
        """Regression: parse() must handle digit-to-uppercase transitions.

        Previously, the regex `([a-z])([A-Z])` missed transitions like
        "3T" in "largeV3Turbo", producing "large-v3turbo" instead of
        "large-v3-turbo". Now `([a-z0-9])([A-Z])` handles these correctly.
        """
        assert ModelSize.parse("largeV3") == ModelSize.LARGE_V3
        assert ModelSize.parse("largeV3Turbo") == ModelSize.LARGE_V3_TURBO

    def test_parse_strips_surrounding_whitespace(self) -> None:
        """Regression: model config should tolerate incidental whitespace."""
        assert ModelSize.parse(" small ") == ModelSize.SMALL
        assert ModelSize.parse("\tlarge_v3_turbo\n") == ModelSize.LARGE_V3_TURBO
