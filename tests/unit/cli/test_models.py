"""Unit tests for CLI models command.

Tests verify:
- List models output format
- Download model validation
- Remove model confirmation
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from audiocore.backends.faster_whisper.model_manager import ModelInfo
from audiocore.cli.models import app

runner = CliRunner()


@pytest.fixture
def mock_manager() -> MagicMock:
    """Create a mock ModelManager."""
    mock = MagicMock()
    mock.list_models.return_value = [
        ModelInfo(
            name="tiny",
            size_mb=75,
            repo_id="guillaumekln/faster-whisper-tiny",
            downloaded=True,
            local_path=Path("/cache/faster-whisper-tiny"),
        ),
        ModelInfo(
            name="base",
            size_mb=150,
            repo_id="guillaumekln/faster-whisper-base",
            downloaded=False,
            local_path=None,
        ),
        ModelInfo(
            name="small",
            size_mb=500,
            repo_id="guillaumekln/faster-whisper-small",
            downloaded=False,
            local_path=None,
        ),
    ]
    return mock


class TestListModels:
    """Test list models command."""

    def test_list_models_shows_all_models(self, mock_manager: MagicMock) -> None:
        """Test list models shows all model sizes."""
        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "tiny" in result.output.lower()
        assert "base" in result.output.lower()
        assert "small" in result.output.lower()

    def test_list_models_shows_download_status(self, mock_manager: MagicMock) -> None:
        """Test list models shows download status."""
        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "downloaded" in result.output.lower()
        assert "not downloaded" in result.output.lower()

    def test_list_models_shows_model_sizes(self, mock_manager: MagicMock) -> None:
        """Test list models shows model sizes in MB/GB."""
        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Sizes are shown
        assert "mb" in result.output.lower() or "75" in result.output

    def test_list_models_shows_cached_path(self, mock_manager: MagicMock) -> None:
        """Test list models shows cached path for downloaded models."""
        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Cached models show their path
        assert "/cache" in result.output or "faster-whisper-tiny" in result.output


class TestDownloadModel:
    """Test download model command."""

    def test_download_model_already_downloaded(self, mock_manager: MagicMock) -> None:
        """Test downloading model that's already downloaded."""
        mock_manager.is_model_downloaded.return_value = True
        mock_manager.get_model_path.return_value = Path("/cache/faster-whisper-tiny")

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["download", "tiny"])

        assert result.exit_code == 0
        assert "already downloaded" in result.output.lower()

    def test_download_model_new_download(self, mock_manager: MagicMock) -> None:
        """Test downloading a new model."""
        mock_manager.is_model_downloaded.return_value = False
        mock_manager.download_model.return_value = Path("/cache/faster-whisper-base")

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["download", "base"])

        assert result.exit_code == 0
        assert "downloaded" in result.output.lower()

    def test_download_model_invalid_model(self, mock_manager: MagicMock) -> None:
        """Test downloading with invalid model name."""
        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["download", "invalid"])

        assert result.exit_code != 0

    def test_download_model_handles_error(self, mock_manager: MagicMock) -> None:
        """Test download handles errors gracefully."""
        from audiocore.errors import ConfigurationError

        mock_manager.is_model_downloaded.return_value = False
        mock_manager.download_model.side_effect = ConfigurationError(
            "Download failed",
            context={},
            suggestions=["Try again"],
        )

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["download", "base"])

        assert result.exit_code == 1


class TestRemoveModel:
    """Test remove model command."""

    def test_remove_model_not_downloaded(self, mock_manager: MagicMock) -> None:
        """Test removing model that's not downloaded."""
        mock_manager.is_model_downloaded.return_value = False

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["remove", "base"])

        assert result.exit_code == 0
        assert "not downloaded" in result.output.lower()

    def test_remove_model_with_confirmation(self, mock_manager: MagicMock) -> None:
        """Test removing model with confirmation."""
        mock_manager.is_model_downloaded.return_value = True
        # Mock list_models for size display
        mock_manager.list_models.return_value = [
            ModelInfo(
                name="base",
                size_mb=150,
                repo_id="guillaumekln/faster-whisper-base",
                downloaded=True,
                local_path=Path("/cache/faster-whisper-base"),
            ),
        ]
        mock_manager.delete_model.return_value = None

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            # Answer "y" to confirmation
            result = runner.invoke(app, ["remove", "base"], input="y\n")

        assert result.exit_code == 0
        assert "removed" in result.output.lower()

    def test_remove_model_with_force_flag(self, mock_manager: MagicMock) -> None:
        """Test removing model with --force flag skips confirmation."""
        mock_manager.is_model_downloaded.return_value = True
        mock_manager.delete_model.return_value = None

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["remove", "base", "--force"])

        assert result.exit_code == 0
        assert "removed" in result.output.lower()

    def test_remove_model_cancelled_confirmation(self, mock_manager: MagicMock) -> None:
        """Test removing model cancelled via confirmation prompt."""
        mock_manager.is_model_downloaded.return_value = True
        mock_manager.list_models.return_value = [
            ModelInfo(
                name="base",
                size_mb=150,
                repo_id="guillaumekln/faster-whisper-base",
                downloaded=True,
                local_path=Path("/cache/faster-whisper-base"),
            ),
        ]

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            # Answer "n" to confirmation
            result = runner.invoke(app, ["remove", "base"], input="n\n")

        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    def test_remove_model_invalid_model(self, mock_manager: MagicMock) -> None:
        """Test removing with invalid model name."""
        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["remove", "invalid"])

        assert result.exit_code != 0

    def test_remove_model_handles_error(self, mock_manager: MagicMock) -> None:
        """Test remove handles errors gracefully."""
        from audiocore.errors import ConfigurationError

        mock_manager.is_model_downloaded.return_value = True
        mock_manager.delete_model.side_effect = ConfigurationError(
            "Failed to delete",
            context={},
            suggestions=["Try again"],
        )

        with patch("audiocore.cli.models.ModelManager", return_value=mock_manager):
            result = runner.invoke(app, ["remove", "base", "--force"])

        assert result.exit_code == 1


class TestModelSizeParsing:
    """Test model size validation."""

    def test_valid_model_sizes(self) -> None:
        """Test all valid model sizes are accepted."""
        from audiocore.cli.models import parse_model_size
        from audiocore.types import ModelSize

        assert parse_model_size("tiny") == ModelSize.TINY.value
        assert parse_model_size("base") == ModelSize.BASE.value
        assert parse_model_size("small") == ModelSize.SMALL.value
        assert parse_model_size("medium") == ModelSize.MEDIUM.value
        assert parse_model_size("large") == ModelSize.LARGE.value

    def test_case_insensitive(self) -> None:
        """Test model size parsing is case-insensitive."""
        from audiocore.cli.models import parse_model_size
        from audiocore.types import ModelSize

        assert parse_model_size("TINY") == ModelSize.TINY.value
        assert parse_model_size("Base") == ModelSize.BASE.value

    def test_invalid_model_size(self) -> None:
        """Test invalid model size raises error."""
        import typer

        from audiocore.cli.models import parse_model_size

        with pytest.raises(typer.BadParameter):
            parse_model_size("huge")


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_model_info_creation(self) -> None:
        """Test ModelInfo can be created."""
        info = ModelInfo(
            name="base",
            size_mb=150,
            repo_id="guillaumekln/faster-whisper-base",
            downloaded=True,
            local_path=Path("/cache/faster-whisper-base"),
        )

        assert info.name == "base"
        assert info.size_mb == 150
        assert info.downloaded is True
        assert Path(info.local_path) == Path("/cache/faster-whisper-base")

    def test_model_info_not_downloaded(self) -> None:
        """Test ModelInfo for not downloaded model."""
        info = ModelInfo(
            name="small",
            size_mb=500,
            repo_id="guillaumekln/faster-whisper-small",
            downloaded=False,
            local_path=None,
        )

        assert info.name == "small"
        assert info.downloaded is False
        assert info.local_path is None


class TestModelsCoverageGaps:
    """Cover GB formatting, already-downloaded-without-path, and remove confirm loop."""

    def test_list_formats_large_model_in_gigabytes(self) -> None:
        manager = MagicMock()
        manager.list_models.return_value = [
            ModelInfo(
                name="large-v3",
                size_mb=1500,
                repo_id="guillaumekln/faster-whisper-large-v3",
                downloaded=False,
                local_path=None,
            )
        ]
        with patch("audiocore.cli.models.ModelManager", return_value=manager):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "1.5 GB" in result.output

    def test_download_already_downloaded_without_known_path(self) -> None:
        manager = MagicMock()
        manager.is_model_downloaded.return_value = True
        manager.get_model_path.return_value = None
        with patch("audiocore.cli.models.ModelManager", return_value=manager):
            result = runner.invoke(app, ["download", "tiny"])

        assert result.exit_code == 0
        assert "already downloaded" in result.output.lower()
        assert "Location" not in result.output

    def test_remove_unconfirmed_when_model_absent_from_list(self) -> None:
        manager = MagicMock()
        manager.is_model_downloaded.return_value = True
        # list_models does not contain the target -> size lookup loop finds nothing.
        manager.list_models.return_value = [
            ModelInfo(
                name="base",
                size_mb=150,
                repo_id="guillaumekln/faster-whisper-base",
                downloaded=True,
                local_path=Path("/cache/base"),
            )
        ]
        with patch("audiocore.cli.models.ModelManager", return_value=manager):
            result = runner.invoke(app, ["remove", "tiny"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.output
        manager.delete_model.assert_not_called()
