"""Tests for backend availability checking."""

import os
from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from audiocore.backends.availability import BackendAvailabilityChecker, BackendStatus
from audiocore.config import AppConfig
from audiocore.config.openai_config import OpenAIConfig
from audiocore.types import BackendType


class TestBackendStatus:
    """Tests for BackendStatus dataclass."""

    def test_create_available_status(self):
        """Test creating an available backend status."""
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

    def test_create_unavailable_status(self):
        """Test creating an unavailable backend status."""
        status = BackendStatus(
            backend_type=BackendType.FASTER_WHISPER,
            available=False,
            reason="faster-whisper not installed",
            suggestion="Install with: pip install faster-whisper",
        )

        assert status.backend_type == BackendType.FASTER_WHISPER
        assert status.available is False
        assert status.reason == "faster-whisper not installed"
        assert status.suggestion == "Install with: pip install faster-whisper"

    def test_default_values(self):
        """Test default None values for reason and suggestion."""
        status = BackendStatus(backend_type=BackendType.OPENAI, available=True)

        assert status.reason is None
        assert status.suggestion is None


class TestBackendAvailabilityChecker:
    """Tests for BackendAvailabilityChecker."""

    def test_init_without_config(self):
        """Test initialization without config."""
        checker = BackendAvailabilityChecker()
        assert checker.config is not None
        assert isinstance(checker.config, AppConfig)

    def test_init_with_config(self):
        """Test initialization with config."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        checker = BackendAvailabilityChecker(config=config)
        assert checker.config == config

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}, clear=True)
    def test_check_openai_with_env_key(self):
        """Test OpenAI availability with environment variable."""
        checker = BackendAvailabilityChecker()
        status = checker.check_backend(BackendType.OPENAI)

        assert status.backend_type == BackendType.OPENAI
        assert status.available is True
        assert "API key" in status.reason

    def test_check_openai_with_config_key(self):
        """Test OpenAI availability with config key."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("sk-test-key")))
        checker = BackendAvailabilityChecker(config=config)
        status = checker.check_backend(BackendType.OPENAI)

        assert status.available is True
        assert "API key" in status.reason

    @patch.dict(os.environ, {}, clear=True)
    def test_check_openai_without_key(self):
        """Test OpenAI availability without API key."""
        config = AppConfig(openai=OpenAIConfig())
        checker = BackendAvailabilityChecker(config=config)
        status = checker.check_backend(BackendType.OPENAI)

        assert status.available is False
        assert "API key not configured" in status.reason
        assert "OPENAI_API_KEY" in status.suggestion

    def test_check_faster_whisper_installed(self):
        """Test faster-whisper availability when installed."""
        mock_fw = MagicMock()
        mock_ct2 = MagicMock()
        mock_ct2.get_supported_compute_types = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": mock_fw, "ctranslate2": mock_ct2}):
            checker = BackendAvailabilityChecker()
            status = checker.check_backend(BackendType.FASTER_WHISPER)

            assert status.backend_type == BackendType.FASTER_WHISPER
            assert status.available is True
            assert "installed" in status.reason

    def test_check_faster_whisper_not_installed(self):
        """Test faster-whisper availability when not installed."""
        original_import = (
            __builtins__["__import__"]
            if isinstance(__builtins__, dict)
            else __builtins__.__import__
        )

        def mock_import(name, *args, **kwargs):
            if name == "faster_whisper":
                raise ImportError("No module named 'faster_whisper'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            checker = BackendAvailabilityChecker()
            status = checker.check_backend(BackendType.FASTER_WHISPER)

            assert status.available is False
            assert "not installed" in status.reason
            assert "pip install" in status.suggestion

    def test_check_backend_auto(self):
        """Test checking AUTO backend type."""
        checker = BackendAvailabilityChecker()
        status = checker.check_backend(BackendType.AUTO)

        assert status.available is False
        assert "AUTO is not a concrete backend type" in status.reason

    def test_check_all(self):
        """Test checking all backends."""
        checker = BackendAvailabilityChecker()
        statuses = checker.check_all()

        assert len(statuses) == 2
        backend_types = [status.backend_type for status in statuses]
        assert BackendType.OPENAI in backend_types
        assert BackendType.FASTER_WHISPER in backend_types

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)
    def test_get_available_backends_both_available(self):
        """Test getting available backends when both are available."""
        mock_fw = MagicMock()
        mock_ct2 = MagicMock()
        mock_ct2.get_supported_compute_types = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": mock_fw, "ctranslate2": mock_ct2}):
            checker = BackendAvailabilityChecker()
            available = checker.get_available_backends()

            assert BackendType.OPENAI in available
            assert BackendType.FASTER_WHISPER in available

    @patch.dict(os.environ, {}, clear=True)
    def test_get_available_backends_none_available(self):
        """Test getting available backends when none available."""
        config = AppConfig(openai=OpenAIConfig())

        original_import = (
            __builtins__["__import__"]
            if isinstance(__builtins__, dict)
            else __builtins__.__import__
        )

        def mock_import(name, *args, **kwargs):
            if name == "faster_whisper":
                raise ImportError("No module named 'faster_whisper'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            checker = BackendAvailabilityChecker(config=config)
            available = checker.get_available_backends()

            assert len(available) == 0

    def test_check_backend_unknown_type(self):
        """Test checking unknown backend type."""
        checker = BackendAvailabilityChecker()

        fake_backend = "unknown_backend"
        status = checker.check_backend(fake_backend)

        assert status.available is False
        assert "Unknown backend type" in status.reason
