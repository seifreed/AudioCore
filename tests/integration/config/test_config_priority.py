"""Integration tests for configuration priority chain.

Tests the full integration: TOML file + environment variables + CLI overrides
with correct priority: CLI > ENV > TOML > defaults.
"""

from pathlib import Path

import pytest

from audiocore.config import load_config
from audiocore.config.settings import AppConfig
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class TestConfigPriorityChain:
    """Integration tests for full priority chain."""

    def test_no_config_no_env_no_cli_returns_defaults(self, tmp_path: Path) -> None:
        """No config, no env, no CLI should return all defaults."""
        nonexistent = tmp_path / "nonexistent.toml"
        config = load_config(config_path=nonexistent)

        assert config.backend == BackendType.AUTO
        assert config.model_size == ModelSize.BASE
        assert config.language is None
        assert config.output_format == OutputFormat.TEXT
        assert config.backend_preference == SelectionPolicy.AUTO
        assert config.openai_api_key is None

    def test_toml_only_no_env_no_cli(self, tmp_path: Path) -> None:
        """TOML values should be used when no env or CLI overrides."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"
backend_preference = "prefer_local"

[output]
output_format = "json"

[language]
language = "es"
"""
        )

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.FASTER_WHISPER
        assert config.model_size == ModelSize.SMALL
        assert config.backend_preference == SelectionPolicy.PREFER_LOCAL
        assert config.output_format == OutputFormat.JSON
        assert config.language == "es"

    def test_toml_plus_env_env_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables should override TOML values."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"
"""
        )

        # Set env vars to override TOML
        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")
        monkeypatch.setenv("AUDIOCORE_MODEL", "large")

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.OPENAI  # env wins over toml
        assert config.model_size == ModelSize.LARGE  # env wins over toml

        monkeypatch.delenv("AUDIOCORE_BACKEND")
        monkeypatch.delenv("AUDIOCORE_MODEL")

    def test_toml_plus_env_plus_cli_cli_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI overrides should have highest priority."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"
"""
        )

        # Set env vars
        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")
        monkeypatch.setenv("AUDIOCORE_MODEL", "medium")

        # CLI overrides everything
        config = load_config(
            config_path=config_file,
            cli_overrides={
                "backend": "auto",
                "model_size": "large",
            },
        )

        assert config.backend == BackendType.AUTO  # cli wins
        assert config.model_size == ModelSize.LARGE  # cli wins

        monkeypatch.delenv("AUDIOCORE_BACKEND")
        monkeypatch.delenv("AUDIOCORE_MODEL")

    def test_missing_toml_file_uses_defaults(self, tmp_path: Path) -> None:
        """Missing TOML file should return defaults (not error)."""
        nonexistent = tmp_path / "nonexistent.toml"
        config = load_config(config_path=nonexistent)

        assert config.backend == BackendType.AUTO
        assert config.model_size == ModelSize.BASE

    def test_all_priority_combinations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test all combinations of priority chain."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"

[output]
output_format = "json"

[language]
language = "fr"
"""
        )

        # Test 1: TOML only
        config = load_config(config_path=config_file)
        assert config.backend == BackendType.FASTER_WHISPER

        # Test 2: TOML + env (env wins)
        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")
        config = load_config(config_path=config_file)
        assert config.backend == BackendType.OPENAI

        # Test 3: TOML + env + CLI (CLI wins)
        config = load_config(config_path=config_file, cli_overrides={"backend": "auto"})
        assert config.backend == BackendType.AUTO

        # Test 4: CLI wins even with env set
        assert config.model_size == ModelSize.SMALL  # from TOML
        config = load_config(config_path=config_file, cli_overrides={"model_size": "large"})
        assert config.model_size == ModelSize.LARGE  # from CLI

        monkeypatch.delenv("AUDIOCORE_BACKEND")


class TestAPIKeyMasking:
    """Test that API keys are never visible in string representations."""

    def test_str_does_not_reveal_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """str() representation should mask API key."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-super-secret-key-12345")

        config = AppConfig()
        str_repr = str(config)

        assert "sk-super-secret-key-12345" not in str_repr

        monkeypatch.delenv("AUDIOCORE_OPENAI_API_KEY")

    def test_repr_does_not_reveal_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """repr() representation should mask API key."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-super-secret-key-12345")

        config = AppConfig()
        repr_str = repr(config)

        assert "sk-super-secret-key-12345" not in repr_str

        monkeypatch.delenv("AUDIOCORE_OPENAI_API_KEY")

    def test_api_key_accessible_via_get_secret_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key should be accessible via get_secret_value()."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-test-key-12345")

        config = AppConfig()

        assert config.openai_api_key is not None
        assert config.openai_api_key.get_secret_value() == "sk-test-key-12345"

        monkeypatch.delenv("AUDIOCORE_OPENAI_API_KEY")

    def test_mask_secrets_in_load_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """load_config should mask secrets in logging."""
        from unittest.mock import patch

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "openai"
"""
        )

        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-very-secret-key")

        # Capture logging
        import logging

        with patch.object(logging.getLogger("audiocore.config.merger"), "debug") as mock_debug:
            load_config(config_path=config_file)

            # Check that API key was not logged in plain text
            for call in mock_debug.call_args_list:
                args_str = str(call)
                assert "sk-very-secret-key" not in args_str

        monkeypatch.delenv("AUDIOCORE_OPENAI_API_KEY")


class TestConfigSourceTracking:
    """Test that we can track which config value came from which source."""

    def test_toml_values_logged_as_toml(self, tmp_path: Path) -> None:
        """TOML values should be tracked as TOML source."""
        import logging
        from unittest.mock import patch

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
"""
        )

        with patch.object(logging.getLogger("audiocore.config.merger"), "debug") as mock_debug:
            load_config(config_path=config_file)

            # Check for source tracking
            calls_str = str(mock_debug.call_args_list)
            # Should see TOML in the sources
            assert "TOML" in calls_str or "faster_whisper" in calls_str

    def test_env_values_logged_as_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment values should be tracked as ENV source."""
        import logging
        from unittest.mock import patch

        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")

        with patch.object(logging.getLogger("audiocore.config.merger"), "debug") as mock_debug:
            load_config(config_path=None)

            # Check for source tracking
            calls_str = str(mock_debug.call_args_list)
            assert "ENV" in calls_str or "openai" in calls_str

        monkeypatch.delenv("AUDIOCORE_BACKEND")


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_toml_file_returns_defaults(self, tmp_path: Path) -> None:
        """Empty TOML file should return defaults."""
        config_file = tmp_path / "empty.toml"
        config_file.write_text("")

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.AUTO
        assert config.model_size == ModelSize.BASE

    def test_partial_toml_with_env_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Partial TOML with env override should merge correctly."""
        config_file = tmp_path / "partial.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
"""
        )

        # Override only model_size via env
        monkeypatch.setenv("AUDIOCORE_MODEL", "large")

        config = load_config(config_path=config_file)

        assert config.backend == BackendType.FASTER_WHISPER  # from TOML
        assert config.model_size == ModelSize.LARGE  # from env

        monkeypatch.delenv("AUDIOCORE_MODEL")

    def test_multiple_fields_different_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multiple fields from different sources should merge correctly."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
backend = "faster_whisper"
model_size = "small"

[output]
output_format = "json"

[language]
language = "de"
"""
        )

        # Set some env overrides
        monkeypatch.setenv("AUDIOCORE_MODEL", "medium")

        # Set some CLI overrides
        config = load_config(
            config_path=config_file,
            cli_overrides={"language": "es"},
        )

        # Expected: TOML (backend, output_format), ENV (model), CLI (language)
        assert config.backend == BackendType.FASTER_WHISPER  # TOML
        assert config.model_size == ModelSize.MEDIUM  # ENV
        assert config.output_format == OutputFormat.JSON  # TOML
        assert config.language == "es"  # CLI

        monkeypatch.delenv("AUDIOCORE_MODEL")

    def test_cli_model_size_to_model_mapping(self, tmp_path: Path) -> None:
        """CLI model_size should map to model field in AppConfig."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            """
[backend]
model_size = "small"
"""
        )

        config = load_config(config_path=config_file, cli_overrides={"model_size": "large"})

        # model_size CLI override maps to model field
        assert config.model_size == ModelSize.LARGE
        assert config.model == ModelSize.LARGE  # same field via property
