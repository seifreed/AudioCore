"""Unit tests for CLI backends command.

Tests verify:
- List backends output format
- Check backends validation
- Exit codes
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from audiocore.cli.backends import app, check_backends, list_backends
from audiocore.backends.availability import BackendStatus
from audiocore.types import BackendType


runner = CliRunner()


@pytest.fixture
def mock_checker() -> MagicMock:
    """Create a mock BackendAvailabilityChecker."""
    mock = MagicMock()
    mock.check_all.return_value = [
        BackendStatus(
            backend_type=BackendType.OPENAI,
            available=True,
            reason="API key configured",
            suggestion=None,
        ),
        BackendStatus(
            backend_type=BackendType.FASTER_WHISPER,
            available=False,
            reason="faster-whisper not installed",
            suggestion="Install with: pip install faster-whisper",
        ),
    ]
    return mock


class TestListBackends:
    """Test list backends command."""

    def test_list_backends_shows_all_backends(self, mock_checker: MagicMock) -> None:
        """Test list backends shows all backends."""
        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "openai" in result.output.lower()
        assert "faster_whisper" in result.output.lower()

    def test_list_backends_shows_available_status(self, mock_checker: MagicMock) -> None:
        """Test list backends shows available status."""
        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "available" in result.output.lower()

    def test_list_backends_shows_unavailable_status(self, mock_checker: MagicMock) -> None:
        """Test list backends shows unavailable backend with reason."""
        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "unavailable" in result.output.lower()
        assert "not installed" in result.output.lower()

    def test_list_backends_shows_suggestions(self, mock_checker: MagicMock) -> None:
        """Test list backends shows suggestions for unavailable backends."""
        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "suggestion" in result.output.lower() or "pip install" in result.output.lower()


class TestCheckBackends:
    """Test check backends command."""

    def test_check_backends_exits_0_when_available(self, mock_checker: MagicMock) -> None:
        """Test check backends exits 0 when at least one backend available."""
        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "available" in result.output.lower()

    def test_check_backends_exits_1_when_none_available(self) -> None:
        """Test check backends exits 1 when no backends available."""
        mock_checker = MagicMock()
        mock_checker.check_all.return_value = [
            BackendStatus(
                backend_type=BackendType.OPENAI,
                available=False,
                reason="OpenAI API key not configured",
                suggestion="Set OPENAI_API_KEY environment variable",
            ),
            BackendStatus(
                backend_type=BackendType.FASTER_WHISPER,
                available=False,
                reason="faster-whisper not installed",
                suggestion="Install with: pip install faster-whisper",
            ),
        ]

        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 1
        assert "no backends available" in result.output.lower()

    def test_check_backends_shows_setup_instructions(self) -> None:
        """Test check backends shows setup instructions when none available."""
        mock_checker = MagicMock()
        mock_checker.check_all.return_value = []

        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 1
        # Should show guidance for setting up backends
        assert "openai" in result.output.lower() or "api key" in result.output.lower()

    def test_check_backends_lists_available_backends(self, mock_checker: MagicMock) -> None:
        """Test check backends lists available backends when found."""
        with patch("audiocore.cli.backends.BackendAvailabilityChecker", return_value=mock_checker):
            result = runner.invoke(app, ["check"])

        assert result.exit_code == 0
        assert "openai" in result.output.lower()


class TestBackendStatus:
    """Test backend status dataclass."""

    def test_backend_status_creation(self) -> None:
        """Test BackendStatus can be created."""
        status = BackendStatus(
            backend_type=BackendType.OPENAI,
            available=True,
            reason="API key configured",
            suggestion=None,
        )

        assert status.backend_type == BackendType.OPENAI
        assert status.available is True
        assert status.reason == "API key configured"
        assert status.suggestion is None

    def test_backend_status_with_suggestion(self) -> None:
        """Test BackendStatus with suggestion."""
        status = BackendStatus(
            backend_type=BackendType.FASTER_WHISPER,
            available=False,
            reason="faster-whisper not installed",
            suggestion="Install with: pip install faster-whisper",
        )

        assert status.backend_type == BackendType.FASTER_WHISPER
        assert status.available is False
        assert "not installed" in status.reason
        assert "pip install" in status.suggestion
