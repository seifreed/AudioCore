"""Unit tests for configuration merger.

Tests priority chain merging, None value handling,
SecretStr masking, and default value extraction.
"""

import os
import tempfile
from pathlib import Path

import pytest
from pydantic import SecretStr

from audiocore.config.merger import (
    _get_defaults,
    load_config,
    mask_secrets,
    merge_configs,
)
from audiocore.config.settings import AppConfig
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class TestGetDefaults:
    """Tests for _get_defaults function."""

    def test_returns_dict_with_all_fields(self) -> None:
        """_get_defaults should return dict for all AppConfig fields."""
        defaults = _get_defaults()

        assert "backend" in defaults
        assert "model" in defaults  # Note: field is 'model', not 'model_size'
        assert "language" in defaults
        assert "output_format" in defaults
        assert "backend_preference" in defaults
        assert "openai_api_key" in defaults

    def test_returns_default_backend(self) -> None:
        """Default backend should be AUTO."""
        defaults = _get_defaults()
        assert defaults["backend"] == BackendType.AUTO

    def test_returns_default_model_size(self) -> None:
        """Default model should be BASE."""
        defaults = _get_defaults()
        assert defaults["model"] == ModelSize.BASE

    def test_returns_default_language_none(self) -> None:
        """Default language should be None."""
        defaults = _get_defaults()
        assert defaults["language"] is None

    def test_returns_default_output_format(self) -> None:
        """Default output format should be TEXT."""
        defaults = _get_defaults()
        assert defaults["output_format"] == OutputFormat.TEXT

    def test_returns_default_backend_preference(self) -> None:
        """Default backend preference should be AUTO."""
        defaults = _get_defaults()
        assert defaults["backend_preference"] == SelectionPolicy.AUTO

    def test_returns_empty_secret_str_for_api_key(self) -> None:
        """Default API key should be empty SecretStr."""
        defaults = _get_defaults()
        assert isinstance(defaults["openai_api_key"], SecretStr)
        assert defaults["openai_api_key"].get_secret_value() == ""


class TestMaskSecrets:
    """Tests for mask_secrets function."""

    def test_masks_secret_str_values(self) -> None:
        """SecretStr values should be replaced with ***REDACTED***."""
        config = {"openai_api_key": SecretStr("sk-secret-123")}
        masked = mask_secrets(config)

        assert masked["openai_api_key"] == "***REDACTED***"

    def test_preserves_non_secret_values(self) -> None:
        """Non-SecretStr values should be preserved."""
        config = {
            "backend": "openai",
            "model_size": "large",
            "language": "en",
        }
        masked = mask_secrets(config)

        assert masked["backend"] == "openai"
        assert masked["model_size"] == "large"
        assert masked["language"] == "en"

    def test_handles_mixed_values(self) -> None:
        """Mixed SecretStr and regular values should be handled correctly."""
        config = {
            "openai_api_key": SecretStr("sk-secret"),
            "backend": "faster_whisper",
            "model_size": "medium",
        }
        masked = mask_secrets(config)

        assert masked["openai_api_key"] == "***REDACTED***"
        assert masked["backend"] == "faster_whisper"
        assert masked["model_size"] == "medium"

    def test_handles_nested_dicts(self) -> None:
        """Nested dicts should be recursively masked."""
        config = {
            "backend": "openai",
            "api_config": {
                "api_key": SecretStr("sk-nested"),
                "timeout": 30,
            },
        }
        masked = mask_secrets(config)

        assert masked["api_config"]["api_key"] == "***REDACTED***"
        assert masked["api_config"]["timeout"] == 30

    def test_handles_empty_dict(self) -> None:
        """Empty dict should return empty dict."""
        assert mask_secrets({}) == {}

    def test_handles_none_value(self) -> None:
        """None values should be preserved."""
        config = {"language": None}
        masked = mask_secrets(config)

        assert masked["language"] is None


class TestMergeConfigs:
    """Tests for merge_configs priority chain."""

    def test_defaults_only(self) -> None:
        """Merging only defaults should return defaults."""
        defaults = {"backend": "auto", "model": "base"}
        result = merge_configs(defaults, {}, {}, {})

        assert result["backend"] == "auto"
        assert result["model"] == "base"

    def test_toml_overrides_defaults(self) -> None:
        """TOML values should override defaults."""
        defaults = {"backend": "auto", "model": "base"}
        toml = {"backend": "faster_whisper"}
        result = merge_configs(defaults, toml, {}, {})

        assert result["backend"] == "faster_whisper"
        assert result["model"] == "base"

    def test_env_overrides_toml(self) -> None:
        """Environment values should override TOML."""
        defaults = {"backend": "auto"}
        toml = {"backend": "faster_whisper"}
        env = {"backend": "openai"}
        result = merge_configs(defaults, toml, env, {})

        assert result["backend"] == "openai"

    def test_cli_overrides_all(self) -> None:
        """CLI values should have highest priority."""
        defaults = {"backend": "auto"}
        toml = {"backend": "faster_whisper"}
        env = {"backend": "openai"}
        cli = {"backend": "auto"}  # Override env
        result = merge_configs(defaults, toml, env, cli)

        assert result["backend"] == "auto"

    def test_full_priority_chain(self) -> None:
        """Full priority chain should work correctly."""
        defaults = {"backend": "auto", "model": "base", "language": None}
        toml = {"backend": "faster_whisper", "model": "small"}
        env = {"backend": "openai"}  # Override backend
        cli = {"model": "large"}  # Override model

        result = merge_configs(defaults, toml, env, cli)

        assert result["backend"] == "openai"  # env wins
        assert result["model"] == "large"  # cli wins
        assert result["language"] is None  # default

    def test_none_values_skipped(self) -> None:
        """None values should be skipped during merge."""
        defaults = {"backend": "auto"}
        toml = {"backend": None}  # None from TOML
        result = merge_configs(defaults, toml, {}, {})

        assert result["backend"] == "auto"  # default retained

    def test_model_size_alias_mapping(self) -> None:
        """model_size should be mapped to model field."""
        defaults = {"model": "base"}
        toml = {"model_size": "large"}  # TOML uses model_size
        result = merge_configs(defaults, toml, {}, {})

        assert result["model"] == "large"

    def test_cli_model_size_mapping(self) -> None:
        """CLI model_size should be mapped to model field."""
        defaults = {"model": "base"}
        cli = {"model_size": "large"}
        result = merge_configs(defaults, {}, {}, cli)

        assert result["model"] == "large"


class TestLoadConfig:
    """Tests for load_config convenience function."""

    def test_loads_defaults(self, tmp_path: Path) -> None:
        """load_config should use defaults when no config present."""
        # Use nonexistent TOML file
        nonexistent = tmp_path / "nonexistent.toml"
        config = load_config(config_path=nonexistent)

        assert config.backend == BackendType.AUTO
        assert config.model_size == ModelSize.BASE

    def test_loads_toml_config(self, tmp_path: Path) -> None:
        """load_config should load TOML configuration."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "medium"
"""
        )

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.FASTER_WHISPER
        assert config.model_size == ModelSize.MEDIUM

    def test_env_overrides_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables should override TOML config."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"
"""
        )

        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.OPENAI  # env overrides toml

        monkeypatch.delenv("AUDIOCORE_BACKEND")

    def test_cli_overrides_all(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI overrides should have highest priority."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"
"""
        )

        monkeypatch.setenv("AUDIOCORE_MODEL", "medium")

        config = load_config(
            config_path=config_file, cli_overrides={"model_size": "large", "backend": "openai"}
        )

        assert config.backend == BackendType.OPENAI  # cli wins
        assert config.model_size == ModelSize.LARGE  # cli wins

        monkeypatch.delenv("AUDIOCORE_MODEL")

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """load_config should accept both Path and string paths."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "openai"
"""
        )

        # Test with string path
        config = load_config(config_path=str(config_file))
        assert config.backend == BackendType.OPENAI

    def test_uses_default_path_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_config should use DEFAULT_CONFIG_PATH when None."""
        # Since default path likely doesn't exist, should return defaults
        config = load_config(config_path=None)

        assert config.backend == BackendType.AUTO
        assert config.model_size == ModelSize.BASE

    def test_partial_toml_config(self, tmp_path: Path) -> None:
        """Partial TOML config should merge with defaults."""
        config_file = tmp_path / "partial.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
"""
        )

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.FASTER_WHISPER
        assert config.model_size == ModelSize.BASE  # default
        assert config.output_format == OutputFormat.TEXT  # default
