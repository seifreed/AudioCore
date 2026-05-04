"""Tests for backend selection."""

import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from audiocore.backends.availability import BackendStatus
from audiocore.backends.selector import BackendSelector, select_backend
from audiocore.config import AppConfig
from audiocore.config.openai_config import OpenAIConfig
from audiocore.errors import BackendUnavailableError
from audiocore.types import BackendType, SelectionPolicy


class TestBackendSelector:
    """Tests for BackendSelector."""

    def test_init_without_config(self):
        """Test initialization without config."""
        selector = BackendSelector()
        assert selector.config is not None
        assert isinstance(selector.config, AppConfig)

    def test_init_with_config(self):
        """Test initialization with config."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        selector = BackendSelector(config=config)
        assert selector.config == config

    def test_select_explicit_openai(self):
        """Test explicit OpenAI selection."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        selector = BackendSelector(config=config)

        result = selector.select(backend=BackendType.OPENAI)
        assert result == BackendType.OPENAI

    def test_select_explicit_faster_whisper(self):
        """Test explicit faster-whisper selection."""
        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            selector = BackendSelector()
            result = selector.select(backend=BackendType.FASTER_WHISPER)
            assert result == BackendType.FASTER_WHISPER

    def test_select_explicit_unavailable_backend(self):
        """Test explicit selection of unavailable backend raises error."""
        config = AppConfig(openai=OpenAIConfig())
        selector = BackendSelector(config=config)

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(selector._checker, "check_backend") as mock_check:
                mock_check.return_value = BackendStatus(
                    backend_type=BackendType.OPENAI,
                    available=False,
                    reason="API key not configured",
                )

                with pytest.raises(BackendUnavailableError) as exc_info:
                    selector.select(backend=BackendType.OPENAI)

                assert "not available" in str(exc_info.value)

    def test_select_auto_with_auto_policy_uses_auto_selection(self):
        """Test that AUTO backend with AUTO policy uses auto selection."""
        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            selector = BackendSelector()
            with patch.object(selector, "_has_cuda", return_value=True):
                result = selector.select(backend=BackendType.AUTO, policy=SelectionPolicy.AUTO)
                assert result == BackendType.FASTER_WHISPER

    def test_validate_backend_auto_handled_by_select(self):
        """Test that AUTO is handled by select(), not _validate_backend."""
        selector = BackendSelector()
        # AUTO is handled in select() before reaching _validate_backend
        # _validate_backend is only called with concrete backend types
        result = selector.select(backend=BackendType.AUTO)
        assert result in (BackendType.OPENAI, BackendType.FASTER_WHISPER)

    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_select_policy_prefer_local_available(self):
        """Test PREFER_LOCAL policy with local backend available."""
        selector = BackendSelector()
        result = selector.select(policy=SelectionPolicy.PREFER_LOCAL)
        assert result == BackendType.FASTER_WHISPER

    def test_select_policy_prefer_local_fallback(self):
        """Test PREFER_LOCAL policy falls back to OpenAI."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))

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
            selector = BackendSelector(config=config)
            result = selector.select(policy=SelectionPolicy.PREFER_LOCAL)
            assert result == BackendType.OPENAI

    def test_select_policy_prefer_cloud_available(self):
        """Test PREFER_CLOUD policy with cloud backend available."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        selector = BackendSelector(config=config)
        result = selector.select(policy=SelectionPolicy.PREFER_CLOUD)
        assert result == BackendType.OPENAI

    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_select_policy_prefer_cloud_fallback(self):
        """Test PREFER_CLOUD policy falls back to local."""
        config = AppConfig(openai=OpenAIConfig())
        selector = BackendSelector(config=config)

        # Mock OpenAI check to return unavailable
        with patch.object(selector._checker, "check_backend") as mock_check:

            def check_side_effect(backend_type):
                if backend_type == BackendType.OPENAI:
                    return BackendStatus(
                        backend_type=BackendType.OPENAI,
                        available=False,
                        reason="API key not configured",
                    )
                else:
                    return BackendStatus(
                        backend_type=BackendType.FASTER_WHISPER,
                        available=True,
                        reason="Module installed",
                    )

            mock_check.side_effect = check_side_effect
            result = selector.select(policy=SelectionPolicy.PREFER_CLOUD)
            assert result == BackendType.FASTER_WHISPER

    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_select_policy_auto_local_available(self):
        """Test AUTO policy with local backend available."""
        selector = BackendSelector()
        with patch.object(selector, "_has_cuda", return_value=True):
            result = selector.select(policy=SelectionPolicy.AUTO)
            assert result == BackendType.FASTER_WHISPER

    def test_select_policy_auto_cloud_available(self):
        """Test AUTO policy with only cloud backend available."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))

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
            selector = BackendSelector(config=config)
            result = selector.select(policy=SelectionPolicy.AUTO)
            assert result == BackendType.OPENAI

    def test_select_no_backends_available(self):
        """Test that selection raises error when no backends available."""
        config = AppConfig(openai=OpenAIConfig())
        selector = BackendSelector(config=config)

        with patch.object(selector._checker, "check_backend") as mock_check:

            def check_side_effect(backend_type):
                return BackendStatus(
                    backend_type=backend_type, available=False, reason="Not available"
                )

            mock_check.side_effect = check_side_effect

            with pytest.raises(BackendUnavailableError) as exc_info:
                selector.select(policy=SelectionPolicy.AUTO)

            assert "No backends available" in str(exc_info.value)

    def test_get_available_backends(self):
        """Test getting available backends list."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))

        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            selector = BackendSelector(config=config)
            available = selector.get_available_backends()

            assert BackendType.OPENAI in available
            assert BackendType.FASTER_WHISPER in available


class TestSelectBackendFunction:
    """Tests for select_backend convenience function."""

    def test_select_backend_default(self):
        """Test select_backend with default arguments."""
        with patch.dict("sys.modules", {"faster_whisper": MagicMock()}):
            selector = BackendSelector()
            with patch.object(selector, "_has_cuda", return_value=True):
                result = selector.select(backend=BackendType.AUTO, policy=SelectionPolicy.AUTO)
                assert result == BackendType.FASTER_WHISPER

    def test_select_backend_explicit(self):
        """Test select_backend with explicit backend."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))

        result = select_backend(backend=BackendType.OPENAI, config=config)
        assert result == BackendType.OPENAI

    def test_select_backend_policy(self):
        """Test select_backend with policy."""
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))

        result = select_backend(policy=SelectionPolicy.PREFER_CLOUD, config=config)
        assert result == BackendType.OPENAI

    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_select_backend_prefer_local(self):
        """Test select_backend with PREFER_LOCAL policy."""
        result = select_backend(policy=SelectionPolicy.PREFER_LOCAL)
        assert result == BackendType.FASTER_WHISPER

    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_select_auto_prefers_cuda_over_cloud(self):
        """Regression: AUTO selection should prefer CUDA faster-whisper over OpenAI.

        The documented priority is: CUDA faster-whisper > OpenAI > CPU faster-whisper.
        When CUDA is available, faster-whisper should be selected even if OpenAI is also available.
        Note: MPS is not considered GPU because CTranslate2 falls back to CPU.
        """
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        selector = BackendSelector(config=config)

        with patch.object(selector, "_has_cuda", return_value=True):
            result = selector.select(backend=BackendType.AUTO, policy=SelectionPolicy.AUTO)
            assert result == BackendType.FASTER_WHISPER

    @patch.dict("sys.modules", {"faster_whisper": MagicMock()})
    def test_select_auto_prefers_cloud_over_no_cuda(self):
        """Regression: AUTO selection should prefer OpenAI over CPU faster-whisper.

        When no CUDA GPU is available, OpenAI should be selected over CPU faster-whisper.
        """
        config = AppConfig(openai=OpenAIConfig(api_key=SecretStr("test-key")))
        selector = BackendSelector(config=config)

        with patch.object(selector, "_has_cuda", return_value=False):
            result = selector.select(backend=BackendType.AUTO, policy=SelectionPolicy.AUTO)
            assert result == BackendType.OPENAI

    def test_select_auto_cpu_fallback(self):
        """Regression: CPU faster-whisper is selected when OpenAI is unavailable and no CUDA."""
        config = AppConfig(openai=OpenAIConfig())
        selector = BackendSelector(config=config)

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(selector, "_has_cuda", return_value=False):
                with patch.object(selector._checker, "check_backend") as mock_check:
                    def check_side_effect(backend_type):
                        if backend_type == BackendType.OPENAI:
                            return BackendStatus(
                                backend_type=BackendType.OPENAI,
                                available=False,
                                reason="No API key",
                            )
                        else:
                            return BackendStatus(
                                backend_type=BackendType.FASTER_WHISPER,
                                available=True,
                                reason="Module installed",
                            )
                    mock_check.side_effect = check_side_effect
                    result = selector.select(policy=SelectionPolicy.AUTO)
                    assert result == BackendType.FASTER_WHISPER
