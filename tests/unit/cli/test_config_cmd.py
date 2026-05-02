"""Unit tests for CLI config command.

Tests verify:
- Show config output
- API key redaction (masking)
- Config path output
"""

from unittest.mock import MagicMock, patch

from pydantic import SecretStr
from typer.testing import CliRunner

from audiocore.cli.config_cmd import app, mask_api_key, mask_secret_str
from audiocore.config import AppConfig
from audiocore.types import BackendType

runner = CliRunner()


class TestMaskApiKey:
    """Test API key masking."""

    def test_mask_openai_key(self) -> None:
        """Test masking OpenAI API key (sk- prefix)."""
        masked = mask_api_key("sk-1234567890abcdef")
        assert masked.startswith("sk-***")
        assert "cdef" in masked

    def test_mask_short_key(self) -> None:
        """Test masking short API keys."""
        masked = mask_api_key("short")
        assert masked == "***"

    def test_mask_none_key(self) -> None:
        """Test masking None key."""
        masked = mask_api_key(None)
        assert masked == "(not set)"

    def test_mask_empty_key(self) -> None:
        """Test masking empty key."""
        masked = mask_api_key("")
        assert masked == "(not set)"

    def test_mask_long_non_openai_key(self) -> None:
        """Test masking long key without sk- prefix."""
        masked = mask_api_key("abcdefghij1234567890")
        assert masked.startswith("abcd***")
        assert "7890" in masked


class TestMaskSecretStr:
    """Test SecretStr masking."""

    def test_mask_secret_str(self) -> None:
        """Test masking SecretStr object."""
        from pydantic import SecretStr

        secret = SecretStr("sk-1234567890abcdef")
        masked = mask_secret_str(secret)

        assert masked.startswith("sk-***")
        assert "cdef" in masked

    def test_mask_non_secret(self) -> None:
        """Test masking non-SecretStr object."""
        masked = mask_secret_str("not a secret")
        assert masked == "not a secret"


class TestShowConfig:
    """Test show config command."""

    def _make_mock_config(self) -> MagicMock:
        """Create a mock AppConfig for testing."""
        mock_config = MagicMock(spec=AppConfig)
        mock_config.backend = BackendType.OPENAI
        mock_config.model = MagicMock()
        mock_config.model.value = "base"
        mock_config.language = None
        mock_config.output_format = MagicMock()
        mock_config.output_format.value = "text"
        mock_config.backend_preference = MagicMock()
        mock_config.backend_preference.value = "auto"
        mock_config.ffprobe_path = "ffprobe"
        mock_config.ffmpeg_path = "ffmpeg"
        mock_config.openai = MagicMock()
        mock_config.openai.api_key = SecretStr("")
        mock_config.openai.organization = None
        mock_config.openai.timeout = 300
        mock_config.openai.max_retries = 2
        mock_config.vad = MagicMock()
        return mock_config

    def test_show_config_displays_backend(self) -> None:
        """Test show config displays backend setting."""
        mock_config = self._make_mock_config()
        mock_config.backend = BackendType.OPENAI

        with patch("audiocore.cli.config_cmd.load_config", return_value=mock_config):
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        assert "openai" in result.output.lower()

    def test_show_config_masks_api_key(self) -> None:
        """Test show config masks API key."""
        mock_config = self._make_mock_config()
        mock_config.openai.api_key = SecretStr("sk-1234567890abcdef")

        with patch("audiocore.cli.config_cmd.load_config", return_value=mock_config):
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        # API key should be masked
        assert "1234567890abcdef" not in result.output

    def test_show_config_displays_language(self) -> None:
        """Test show config displays language setting."""
        mock_config = self._make_mock_config()
        mock_config.language = "en"

        with patch("audiocore.cli.config_cmd.load_config", return_value=mock_config):
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        assert "en" in result.output

    def test_show_config_displays_vad_settings(self) -> None:
        """Test show config displays VAD settings."""
        mock_config = self._make_mock_config()
        mock_config.vad.min_segment_duration = 0.5
        mock_config.vad.max_segment_duration = 30.0
        mock_config.vad.speech_threshold = 0.5
        mock_config.vad.silence_threshold = 0.3

        with patch("audiocore.cli.config_cmd.load_config", return_value=mock_config):
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        # VAD settings should be shown
        assert "vad" in result.output.lower()


class TestConfigPath:
    """Test config path command."""

    def test_config_path_displays_default_path(self) -> None:
        """Test config path displays default path."""
        result = runner.invoke(app, ["path"])

        assert result.exit_code == 0
        assert "configuration" in result.output.lower()

    def test_config_path_shows_priority(self) -> None:
        """Test config path shows configuration priority."""
        result = runner.invoke(app, ["path"])

        assert result.exit_code == 0
        assert "priority" in result.output.lower()
        # Should mention environment variables and config file
        assert "environment" in result.output.lower() or "env" in result.output.lower()


class TestConfigErrorHandling:
    """Test error handling in config commands."""

    def test_show_config_handles_error(self) -> None:
        """Test show config handles configuration errors."""
        with patch("audiocore.cli.config_cmd.load_config") as mock_load:
            mock_load.side_effect = Exception("Config load failed")

            result = runner.invoke(app, ["show"])

        assert result.exit_code == 1
        assert "error" in result.output.lower()


class TestShowConfigUsesLoadConfig:
    """Regression: config show must use load_config(), not raw AppConfig()."""

    def test_show_config_calls_load_config(self) -> None:
        """show_config should call load_config() instead of AppConfig()."""
        mock_config = MagicMock(spec=AppConfig)
        mock_config.backend = BackendType.OPENAI
        mock_config.model = MagicMock()
        mock_config.model.value = "base"
        mock_config.language = None
        mock_config.output_format = MagicMock()
        mock_config.output_format.value = "text"
        mock_config.backend_preference = MagicMock()
        mock_config.backend_preference.value = "auto"
        mock_config.ffprobe_path = "ffprobe"
        mock_config.ffmpeg_path = "ffmpeg"
        mock_config.openai = MagicMock()
        mock_config.openai.api_key = SecretStr("")
        mock_config.openai.organization = None
        mock_config.openai.timeout = 300
        mock_config.openai.max_retries = 2
        mock_config.vad = MagicMock()

        with patch("audiocore.cli.config_cmd.load_config", return_value=mock_config) as mock_load:
            result = runner.invoke(app, ["show"])

        assert result.exit_code == 0
        mock_load.assert_called_once()
