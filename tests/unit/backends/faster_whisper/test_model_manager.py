"""Unit tests for ModelManager and HuggingFace Hub integration.

Tests model download, caching, listing, and deletion with mocked
huggingface_hub.
"""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiocore.backends.faster_whisper.model_manager import (
    DEFAULT_CACHE_DIR,
    MODEL_REPOS,
    MODEL_SIZES_MB,
    ModelInfo,
    ModelManager,
    get_model_info,
)
from audiocore.errors.backend import BackendUnavailableError
from audiocore.errors.config import ConfigurationError
from audiocore.types.backend import ModelSize


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_model_info_creation(self) -> None:
        """Should create ModelInfo with all fields."""
        info = ModelInfo(
            name="base",
            size_mb=150,
            repo_id="guillaumekln/faster-whisper-base",
            filename="model.bin",
            downloaded=True,
            local_path=Path("/path/to/model"),
        )
        assert info.name == "base"
        assert info.size_mb == 150
        assert info.repo_id == "guillaumekln/faster-whisper-base"
        assert info.filename == "model.bin"
        assert info.downloaded is True
        assert info.local_path == Path("/path/to/model")

    def test_model_info_defaults(self) -> None:
        """ModelInfo should have default filename."""
        info = ModelInfo(
            name="tiny",
            size_mb=75,
            repo_id="guillaumekln/faster-whisper-tiny",
        )
        assert info.filename == "model.bin"
        assert info.downloaded is False
        assert info.local_path is None


class TestModelConstants:
    """Test model constants."""

    def test_model_repos_has_all_sizes(self) -> None:
        """MODEL_REPOS should have all model sizes."""
        assert ModelSize.TINY.value in MODEL_REPOS
        assert ModelSize.BASE.value in MODEL_REPOS
        assert ModelSize.SMALL.value in MODEL_REPOS
        assert ModelSize.MEDIUM.value in MODEL_REPOS
        assert ModelSize.LARGE.value in MODEL_REPOS

    def test_model_sizes_has_all_sizes(self) -> None:
        """MODEL_SIZES_MB should have all model sizes."""
        assert ModelSize.TINY.value in MODEL_SIZES_MB
        assert ModelSize.BASE.value in MODEL_SIZES_MB
        assert ModelSize.SMALL.value in MODEL_SIZES_MB
        assert ModelSize.MEDIUM.value in MODEL_SIZES_MB
        assert ModelSize.LARGE.value in MODEL_SIZES_MB

    def test_default_cache_dir(self) -> None:
        """DEFAULT_CACHE_DIR should be user home cache."""
        assert ".cache" in str(DEFAULT_CACHE_DIR)
        assert "huggingface" in str(DEFAULT_CACHE_DIR)


class TestModelManagerSingleton:
    """Test ModelManager singleton pattern."""

    def test_singleton_returns_same_instance(self) -> None:
        """ModelManager should return same instance."""
        manager1 = ModelManager()
        manager2 = ModelManager()
        assert manager1 is manager2

    def test_singleton_thread_safety(self) -> None:
        """ModelManager should be thread-safe."""
        # Reset singleton for test
        ModelManager._instance = None

        instances: list[ModelManager] = []

        def create_instance() -> None:
            instances.append(ModelManager())

        threads = [threading.Thread(target=create_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All instances should be the same
        assert all(inst is instances[0] for inst in instances)

        # Cleanup
        ModelManager._instance = None

    def test_singleton_preserves_cache_dir(self) -> None:
        """Singleton should preserve first cache_dir and reject different one."""
        # Reset singleton
        ModelManager._instance = None

        manager1 = ModelManager(cache_dir=Path("/custom/cache"))
        assert manager1.cache_dir == Path("/custom/cache")

        # Creating with same cache_dir is fine
        manager2 = ModelManager(cache_dir=Path("/custom/cache"))
        assert manager2.cache_dir == Path("/custom/cache")

        # Creating with different cache_dir should raise ValueError
        with pytest.raises(ValueError, match="already initialized"):
            ModelManager(cache_dir=Path("/other/cache"))

        # Creating without cache_dir returns existing instance
        manager3 = ModelManager()
        assert manager3.cache_dir == Path("/custom/cache")

        # Cleanup
        ModelManager._instance = None

    def test_clear_resets_state(self) -> None:
        """clear() should clear model cache."""
        manager = ModelManager()
        manager._models["test"] = "value"
        manager.clear()
        assert len(manager._models) == 0

    def test_clear_resets_singleton(self) -> None:
        """Regression: clear() must reset singleton so a fresh instance can be
        created with a different cache_dir.

        Previously, clear() only cleared _models but left _instance intact,
        preventing tests from creating ModelManager(custom_cache_dir).
        """
        manager = ModelManager()
        original_id = id(manager)
        manager.clear()

        # After clear(), a new ModelManager() should be a fresh instance
        new_manager = ModelManager()
        assert id(new_manager) != original_id


class TestModelManagerDownloadModel:
    """Test ModelManager.download_model."""

    def test_download_invalid_model_raises_error(self) -> None:
        """Invalid model name should raise ConfigurationError."""
        manager = ModelManager()
        with pytest.raises(ConfigurationError) as exc_info:
            manager.download_model("invalid_model")
        assert "Invalid model name" in str(exc_info.value)

    def test_download_invalid_model_suggests_valid_models(self) -> None:
        """Invalid model error should include valid models in context."""
        manager = ModelManager()
        with pytest.raises(ConfigurationError) as exc_info:
            manager.download_model("invalid")
        error = exc_info.value
        assert "valid_models" in error.context
        assert len(error.context["valid_models"]) > 0
        # Check that valid models are mentioned in error

    def test_download_model_success(self, tmp_path: Path) -> None:
        """Should download model from HuggingFace Hub."""
        # Reset singleton
        ModelManager._instance = None

        # Setup mock
        model_path = tmp_path / "model.bin"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.touch()

        # Create mock huggingface_hub module
        mock_hf = MagicMock()
        mock_hf.hf_hub_download = MagicMock(return_value=str(model_path))

        manager = ModelManager(cache_dir=tmp_path)

        # Mock the import inside download_model
        with patch.dict("sys.modules", {"huggingface_hub": mock_hf}):
            result = manager.download_model("base")

        assert result == model_path
        mock_hf.hf_hub_download.assert_called_once()

        # Cleanup
        ModelManager._instance = None

    def test_download_already_cached(self, tmp_path: Path) -> None:
        """Should return cached path if already downloaded."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        # Create fake cached model
        repo_id = MODEL_REPOS["base"]
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = tmp_path / cache_folder_name / "snapshots" / "abc123"
        cache_path.mkdir(parents=True, exist_ok=True)
        model_file = cache_path / "model.bin"
        model_file.touch()

        result = manager.download_model("base")

        # Should NOT call hf_hub_download
        assert result == model_file

        # Cleanup
        ModelManager._instance = None


class TestModelManagerGetModelPath:
    """Test ModelManager.get_model_path."""

    def test_get_model_path_not_cached(self, tmp_path: Path) -> None:
        """Should return None if model not cached."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)
        result = manager.get_model_path("base")

        assert result is None

        # Cleanup
        ModelManager._instance = None

    def test_get_model_path_cached(self, tmp_path: Path) -> None:
        """Should return path if model is cached."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        # Create fake cached model
        repo_id = MODEL_REPOS["base"]
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = tmp_path / cache_folder_name / "snapshots" / "abc123"
        cache_path.mkdir(parents=True, exist_ok=True)
        model_file = cache_path / "model.bin"
        model_file.touch()

        result = manager.get_model_path("base")

        assert result == model_file

        # Cleanup
        ModelManager._instance = None

    def test_get_model_path_invalid_model(self) -> None:
        """Should return None for invalid model name."""
        manager = ModelManager()
        result = manager.get_model_path("invalid")
        assert result is None


class TestModelManagerListModels:
    """Test ModelManager.list_models."""

    def test_list_models_returns_all_models(self) -> None:
        """list_models should return all model sizes."""
        manager = ModelManager()
        models = manager.list_models()

        model_names = [m.name for m in models]
        assert "tiny" in model_names
        assert "base" in model_names
        assert "small" in model_names
        assert "medium" in model_names
        assert "large" in model_names

    def test_list_models_sizes(self) -> None:
        """list_models should return correct sizes."""
        manager = ModelManager()
        models = manager.list_models()

        sizes = {m.name: m.size_mb for m in models}
        assert sizes["tiny"] == 75
        assert sizes["base"] == 150
        assert sizes["small"] == 500
        assert sizes["medium"] == 1500
        assert sizes["large"] == 3000

    def test_list_models_repo_ids(self) -> None:
        """list_models should return correct repo IDs."""
        manager = ModelManager()
        models = manager.list_models()

        repos = {m.name: m.repo_id for m in models}
        assert "Systran/faster-whisper-tiny" in repos["tiny"]
        assert "Systran/faster-whisper-base" in repos["base"]


class TestModelManagerDeleteModel:
    """Test ModelManager.delete_model."""

    def test_delete_invalid_model_raises_error(self) -> None:
        """Invalid model name should raise ConfigurationError."""
        manager = ModelManager()
        with pytest.raises(ConfigurationError) as exc_info:
            manager.delete_model("invalid_model")
        assert "Invalid model name" in str(exc_info.value)

    def test_delete_not_cached_raises_error(self, tmp_path: Path) -> None:
        """Deleting uncached model should raise error."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        with pytest.raises(ConfigurationError) as exc_info:
            manager.delete_model("base")
        assert "not found in cache" in str(exc_info.value).lower()

        # Cleanup
        ModelManager._instance = None

    def test_delete_cached_model(self, tmp_path: Path) -> None:
        """Should delete cached model directory."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        # Create fake cached model
        repo_id = MODEL_REPOS["base"]
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = tmp_path / cache_folder_name
        cache_path.mkdir(parents=True, exist_ok=True)

        # Delete should succeed
        manager.delete_model("base")

        # Cache directory should be removed
        assert not cache_path.exists()

        # Cleanup
        ModelManager._instance = None


class TestModelManagerIsModelDownloaded:
    """Test ModelManager.is_model_downloaded."""

    def test_is_model_downloaded_not_cached(self, tmp_path: Path) -> None:
        """Should return False if model not cached."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)
        result = manager.is_model_downloaded("base")

        assert result is False

        # Cleanup
        ModelManager._instance = None

    def test_is_model_downloaded_cached(self, tmp_path: Path) -> None:
        """Should return True if model is cached."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        # Create fake cached model
        repo_id = MODEL_REPOS["base"]
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = tmp_path / cache_folder_name / "snapshots" / "abc123"
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / "model.bin").touch()

        result = manager.is_model_downloaded("base")

        assert result is True

        # Cleanup
        ModelManager._instance = None

    def test_is_model_downloaded_invalid(self) -> None:
        """Should return False for invalid model name."""
        manager = ModelManager()
        result = manager.is_model_downloaded("invalid")
        assert result is False


class TestGetModelInfo:
    """Test get_model_info convenience function."""

    def test_get_model_info_valid(self) -> None:
        """Should return ModelInfo for valid model."""
        info = get_model_info("base")
        assert info is not None
        assert info.name == "base"
        assert info.size_mb == 150

    def test_get_model_info_invalid(self) -> None:
        """Should return None for invalid model."""
        info = get_model_info("invalid")
        assert info is None


class TestModelManagerErrorHandling:
    """Test ModelManager error handling."""

    @patch.dict("sys.modules", {"huggingface_hub": None})
    def test_download_without_huggingface_raises_error(self, tmp_path: Path) -> None:
        """Should raise BackendUnavailableError if huggingface-hub not installed."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        with pytest.raises(BackendUnavailableError) as exc_info:
            manager.download_model("base")
        assert "huggingface-hub not installed" in str(exc_info.value).lower()

        # Cleanup
        ModelManager._instance = None

    def test_download_with_progress_callback(self, tmp_path: Path) -> None:
        """Should support progress callback during download."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager(cache_dir=tmp_path)

        # Create fake cached model (so download is skipped)
        repo_id = MODEL_REPOS["base"]
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = tmp_path / cache_folder_name / "snapshots" / "abc123"
        cache_path.mkdir(parents=True, exist_ok=True)
        (cache_path / "model.bin").touch()

        progress_calls: list[float] = []

        def progress_callback(progress: float) -> None:
            progress_calls.append(progress)

        result = manager.download_model("base", progress_callback=progress_callback)

        # Should return path without calling progress (already cached)
        assert result is not None
        # Progress callback not called for cached models
        assert len(progress_calls) == 0

        # Cleanup
        ModelManager._instance = None


class TestModelManagerCacheDir:
    """Test ModelManager cache directory handling."""

    def test_default_cache_dir(self) -> None:
        """Should use default cache directory."""
        # Reset singleton
        ModelManager._instance = None

        manager = ModelManager()
        assert manager.cache_dir == DEFAULT_CACHE_DIR

        # Cleanup
        ModelManager._instance = None

    def test_custom_cache_dir(self, tmp_path: Path) -> None:
        """Should use custom cache directory."""
        # Reset singleton
        ModelManager._instance = None

        custom_cache = tmp_path / "custom" / "cache"
        manager = ModelManager(cache_dir=custom_cache)

        assert manager.cache_dir == custom_cache

        # Cleanup
        ModelManager._instance = None
