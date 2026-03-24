"""Tests for SelectionPolicy enum."""

import pytest

from audiocore.types import SelectionPolicy


class TestSelectionPolicy:
    """Tests for SelectionPolicy enum."""

    def test_values(self) -> None:
        """Test that SelectionPolicy has correct values."""
        assert SelectionPolicy.PREFER_LOCAL.value == "prefer_local"
        assert SelectionPolicy.PREFER_CLOUD.value == "prefer_cloud"
        assert SelectionPolicy.AUTO.value == "auto"

    def test_str_enum_inheritance(self) -> None:
        """Test that SelectionPolicy inherits from str and Enum for JSON serialization."""
        assert isinstance(SelectionPolicy.AUTO, str)
        assert SelectionPolicy.AUTO == "auto"

    def test_parse_case_insensitive(self) -> None:
        """Test parse() method with various case formats."""
        assert SelectionPolicy.parse("prefer_local") == SelectionPolicy.PREFER_LOCAL
        assert SelectionPolicy.parse("PREFER_LOCAL") == SelectionPolicy.PREFER_LOCAL
        assert SelectionPolicy.parse("PreferLocal") == SelectionPolicy.PREFER_LOCAL
        assert SelectionPolicy.parse("prefer-local") == SelectionPolicy.PREFER_LOCAL
        assert SelectionPolicy.parse("prefer cloud") == SelectionPolicy.PREFER_CLOUD
        assert SelectionPolicy.parse("Prefer Cloud") == SelectionPolicy.PREFER_CLOUD
        assert SelectionPolicy.parse("auto") == SelectionPolicy.AUTO
        assert SelectionPolicy.parse("AUTO") == SelectionPolicy.AUTO

    def test_parse_invalid_value(self) -> None:
        """Test parse() raises ValueError for invalid values."""
        with pytest.raises(ValueError) as exc_info:
            SelectionPolicy.parse("unknown_policy")

        assert "Invalid selection policy" in str(exc_info.value)
        assert "prefer_local" in str(exc_info.value)
        assert "prefer_cloud" in str(exc_info.value)
        assert "auto" in str(exc_info.value)

    def test_all_values_exist(self) -> None:
        """Test that all expected values exist."""
        values = [m.value for m in SelectionPolicy]
        assert "prefer_local" in values
        assert "prefer_cloud" in values
        assert "auto" in values
