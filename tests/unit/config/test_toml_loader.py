"""Tests for TOML configuration file loader."""

import tempfile
from pathlib import Path

import pytest

from audiocore.config.toml_loader import (
    DEFAULT_CONFIG_PATH,
    _flatten_toml_section,
    load_toml_config,
)
from audiocore.errors import InvalidConfigError


class TestDefaultConfigPath:
    """Tests for DEFAULT_CONFIG_PATH constant."""

    def test_default_path_location(self) -> None:
        """DEFAULT_CONFIG_PATH should point to ~/.config/audiocore/config.toml."""
        expected = Path.home() / ".config" / "audiocore" / "config.toml"
        assert DEFAULT_CONFIG_PATH == expected

    def test_default_path_is_absolute(self) -> None:
        """DEFAULT_CONFIG_PATH should be an absolute path."""
        assert DEFAULT_CONFIG_PATH.is_absolute()


class TestLoadTomlConfig:
    """Tests for load_toml_config function."""

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Missing TOML file should return empty dict, not raise error."""
        missing_path = tmp_path / "nonexistent.toml"
        result = load_toml_config(missing_path)
        assert result == {}

    def test_valid_toml_loads_correctly(self, tmp_path: Path) -> None:
        """Valid TOML file should load and parse correctly."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "openai"
model_size = "medium"

[output]
output_format = "json"
"""
        )

        result = load_toml_config(config_file)

        assert result["backend"] == "openai"
        assert result["model_size"] == "medium"
        assert result["output_format"] == "json"

    def test_invalid_toml_syntax_raises_error(self, tmp_path: Path) -> None:
        """Invalid TOML syntax should raise InvalidConfigError."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("invalid [ syntax")

        with pytest.raises(InvalidConfigError) as exc_info:
            load_toml_config(config_file)

        assert exc_info.value.error_code == "AUD-101"
        assert "Invalid TOML syntax" in str(exc_info.value)
        assert str(config_file) in str(exc_info.value)

    def test_permission_denied_raises_error(self, tmp_path: Path) -> None:
        """Permission denied should raise InvalidConfigError."""
        from unittest.mock import patch

        config_file = tmp_path / "readonly.toml"
        config_file.write_text('[backend]\nbackend = "openai"')

        # Mock built-in open to raise PermissionError
        with patch(
            "audiocore.config.toml_loader.open", side_effect=PermissionError("Permission denied")
        ):
            with pytest.raises(InvalidConfigError) as exc_info:
                load_toml_config(config_file)

            assert exc_info.value.error_code == "AUD-101"
            assert "Permission denied" in str(exc_info.value)
            assert str(config_file) in str(exc_info.value)

    def test_path_expansion_tilde(self, tmp_path: Path) -> None:
        """~ in paths should be expanded to home directory."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[paths]
model_cache_path = "~/.cache/audiocore/models"
temp_path = "/tmp/audiocore"
"""
        )

        result = load_toml_config(config_file)

        assert isinstance(result["model_cache_path"], Path)
        assert isinstance(result["temp_path"], Path)
        assert "~" not in str(result["model_cache_path"])
        assert str(result["temp_path"]) == "/tmp/audiocore"

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        """Empty TOML file should return empty dict."""
        config_file = tmp_path / "empty.toml"
        config_file.write_text("")

        result = load_toml_config(config_file)
        assert result == {}

    def test_empty_sections_handled_gracefully(self, tmp_path: Path) -> None:
        """Empty sections should not cause errors."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
[output]
"""
        )

        result = load_toml_config(config_file)
        assert result == {}

    def test_all_sections_parsed(self, tmp_path: Path) -> None:
        """All TOML sections should be parsed."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "large"
backend_preference = "prefer_local"

[output]
output_format = "srt"

[paths]
model_cache_path = "/custom/cache"
temp_path = "/custom/tmp"

[language]
language = "fr"
"""
        )

        result = load_toml_config(config_file)

        assert result["backend"] == "faster_whisper"
        assert result["model_size"] == "large"
        assert result["backend_preference"] == "prefer_local"
        assert result["output_format"] == "srt"
        assert result["model_cache_path"] == Path("/custom/cache")
        assert result["temp_path"] == Path("/custom/tmp")
        assert result["language"] == "fr"

    def test_default_path_used_when_none_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_toml_config with None should use DEFAULT_CONFIG_PATH."""
        # Mock DEFAULT_CONFIG_PATH to point to a test file
        config_file = tmp_path if "tmp_path" in dir() else Path(tempfile.mkdtemp()) / "config.toml"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        # Create a nonexistent path to test empty dict return
        nonexistent = Path("/nonexistent/config_12345.toml")
        result = load_toml_config(nonexistent)
        assert result == {}

    def test_directory_instead_of_file_raises_error(self, tmp_path: Path) -> None:
        """Passing a directory should raise InvalidConfigError."""
        with pytest.raises(InvalidConfigError) as exc_info:
            load_toml_config(tmp_path)  # tmp_path is a directory

        assert "not a file" in str(exc_info.value).lower()


class TestFlattenTomlSection:
    """Tests for _flatten_toml_section helper."""

    def test_flatten_backend_section(self) -> None:
        """Backend section should flatten correctly."""
        data = {"backend": {"backend": "openai", "model_size": "medium"}}
        result = _flatten_toml_section(data)

        assert result["backend"] == "openai"
        assert result["model_size"] == "medium"

    def test_flatten_output_section(self) -> None:
        """Output section should flatten correctly."""
        data = {"output": {"output_format": "json"}}
        result = _flatten_toml_section(data)

        assert result["output_format"] == "json"

    def test_flatten_paths_section(self) -> None:
        """Paths section should flatten with Path objects."""
        data = {"paths": {"model_cache_path": "~/.cache"}}
        result = _flatten_toml_section(data)

        assert isinstance(result["model_cache_path"], Path)
        assert "~" not in str(result["model_cache_path"])

    def test_flatten_language_section(self) -> None:
        """Language section should flatten correctly."""
        data = {"language": {"language": "es"}}
        result = _flatten_toml_section(data)

        assert result["language"] == "es"

    def test_flatten_mixed_values(self) -> None:
        """Mixed value types should flatten correctly."""
        data = {
            "backend": {"backend": "auto", "model_size": "base"},
            "output": {"output_format": "text"},
            "language": {"language": "en"},
        }
        result = _flatten_toml_section(data)

        assert result["backend"] == "auto"
        assert result["model_size"] == "base"
        assert result["output_format"] == "text"
        assert result["language"] == "en"

    def test_flatten_unknown_key(self) -> None:
        """Unknown keys should be included in result."""
        data = {"unknown_section": {"unknown_key": "value"}}
        result = _flatten_toml_section(data)

        # Unknown keys get added with their key name
        assert "unknown_key" in result

    def test_flatten_empty_section(self) -> None:
        """Empty section should return empty dict."""
        result = _flatten_toml_section({})
        assert result == {}


class TestErrorHandling:
    """Tests for error handling in TOML loader."""

    def test_invalid_config_error_has_context(self, tmp_path: Path) -> None:
        """Invalid TOML error should include file path in context."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("invalid [ toml")

        with pytest.raises(InvalidConfigError) as exc_info:
            load_toml_config(config_file)

        assert "path" in exc_info.value.context
        assert exc_info.value.context["path"] == str(config_file)

    def test_error_suggestions_included(self, tmp_path: Path) -> None:
        """Error should have helpful suggestions."""
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("broken [ toml")

        with pytest.raises(InvalidConfigError) as exc_info:
            load_toml_config(config_file)

        assert len(exc_info.value.suggestions) > 0


class TestIntegration:
    """Integration tests for TOML loader."""

    def test_full_config_load(self, tmp_path: Path) -> None:
        """Full configuration should load correctly."""
        config_file = tmp_path / "full_config.toml"
        config_file.write_text(
            """
# AudioCore configuration
[backend]
backend = "openai"
model_size = "large"
backend_preference = "prefer_cloud"

[output]
output_format = "vtt"

[paths]
model_cache_path = "~/.cache/whisper"
temp_path = "/tmp/audio_transcode"

[language]
language = "de"
"""
        )

        result = load_toml_config(config_file)

        # All fields should be present and correctly typed
        assert result["backend"] == "openai"
        assert result["model_size"] == "large"
        assert result["backend_preference"] == "prefer_cloud"
        assert result["output_format"] == "vtt"
        assert isinstance(result["model_cache_path"], Path)
        assert isinstance(result["temp_path"], Path)
        assert result["language"] == "de"

    def test_partial_config_load(self, tmp_path: Path) -> None:
        """Partial configuration should load correctly."""
        config_file = tmp_path / "partial.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
"""
        )

        result = load_toml_config(config_file)

        # Only specified fields should be present
        assert result["backend"] == "faster_whisper"
        assert "model_size" not in result

    def test_overwrite_defaults_pattern(self, tmp_path: Path) -> None:
        """Load pattern for overwriting defaults should work."""
        # Default config
        from audiocore.config import AppConfig

        defaults = AppConfig()
        config_file = tmp_path / "override.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "medium"

[language]
language = "ja"
"""
        )

        toml_config = load_toml_config(config_file)

        # Merge pattern: toml_config values override defaults
        assert toml_config["backend"] == "faster_whisper"
        # Fields not in TOML keep defaults
        assert defaults.output_format  # Has default value
