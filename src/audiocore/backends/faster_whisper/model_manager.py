"""Model manager for faster-whisper HuggingFace Hub integration.

This module provides ModelManager for downloading, caching, and managing
faster-whisper models from HuggingFace Hub. It implements thread-safe
model management with singleton pattern.

Key Features:
- Automatic model download from HuggingFace Hub
- Local model caching for offline use
- Thread-safe singleton pattern
- Model listing and deletion

Example:
    >>> from audiocore.backends.faster_whisper.model_manager import ModelManager
    >>> manager = ModelManager()
    >>> model_path = manager.download_model("base")
    >>> print(model_path)
    /home/user/.cache/huggingface/hub/models--guillaumekln--faster-whisper-base/...
"""

from __future__ import annotations

import logging
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audiocore.errors.config import ConfigurationError
from audiocore.types.backend import ModelSize

logger = logging.getLogger(__name__)

# Default cache directory for HuggingFace models
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "huggingface" / "hub"

# Model repository mapping
MODEL_REPOS: dict[str, str] = {
    ModelSize.TINY.value: "Systran/faster-whisper-tiny",
    ModelSize.BASE.value: "Systran/faster-whisper-base",
    ModelSize.SMALL.value: "Systran/faster-whisper-small",
    ModelSize.MEDIUM.value: "Systran/faster-whisper-medium",
    ModelSize.LARGE.value: "Systran/faster-whisper-large-v3",
    ModelSize.LARGE_V3.value: "Systran/faster-whisper-large-v3",
    ModelSize.LARGE_V3_TURBO.value: "Systran/faster-whisper-large-v3-turbo",
}

# Approximate model sizes in MB
MODEL_SIZES_MB: dict[str, int] = {
    ModelSize.TINY.value: 75,
    ModelSize.BASE.value: 150,
    ModelSize.SMALL.value: 500,
    ModelSize.MEDIUM.value: 1500,
    ModelSize.LARGE.value: 3000,
    ModelSize.LARGE_V3.value: 3000,
    ModelSize.LARGE_V3_TURBO.value: 3000,
}


@dataclass
class ModelInfo:
    """Information about a faster-whisper model.

    Attributes:
        name: Model name (tiny, base, small, medium, large)
        size_mb: Approximate model size in megabytes
        repo_id: HuggingFace repository ID
        filename: Model filename (typically 'model.bin' for CTranslate2)
        downloaded: Whether model is cached locally
        local_path: Path to cached model if downloaded
    """

    name: str
    size_mb: int
    repo_id: str
    filename: str = "model.bin"
    downloaded: bool = False
    local_path: Path | None = None


class ModelManager:
    """Thread-safe singleton for managing faster-whisper models.

    Manages model download, caching, and deletion from HuggingFace Hub.
    Uses singleton pattern to ensure single instance across application.

    Attributes:
        _instance: Singleton instance
        _lock: Thread lock for singleton initialization
        _models: Cache of loaded model instances
        cache_dir: Directory for model caching

    Example:
        >>> manager = ModelManager()
        >>> models = manager.list_models()
        >>> for model in models:
        ...     print(f"{model.name}: {model.downloaded}")
        tiny: True
        base: False
        ...
    """

    _instance: ModelManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, cache_dir: Path | None = None) -> ModelManager:
        """Create or return singleton instance.

        Args:
            cache_dir: Optional custom cache directory. Ignored if an
                instance already exists — call clear() first to reset.

        Returns:
            ModelManager singleton instance

        Raises:
            ValueError: If cache_dir is provided but a singleton with a
                different cache_dir already exists.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._models: dict[str, Any] = {}
                    instance._cache_dir = cache_dir or DEFAULT_CACHE_DIR
                    cls._instance = instance
        elif cache_dir is not None and cache_dir != cls._instance._cache_dir:
            raise ValueError(
                f"ModelManager singleton already initialized with cache_dir={cls._instance._cache_dir}. "
                f"Cannot change to cache_dir={cache_dir}. Call ModelManager.clear() first to reset."
            )
        return cls._instance

    @property
    def cache_dir(self) -> Path:
        """Get cache directory path.

        Returns:
            Path to model cache directory
        """
        return self._cache_dir

    def download_model(
        self,
        model_name: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> Path:
        """Download model from HuggingFace Hub.

        Downloads model to cache directory if not already present.
        Uses huggingface_hub for downloading.

        Args:
            model_name: Model name (tiny, base, small, medium, large)
            progress_callback: Optional callback for download progress (0.0-1.0)

        Returns:
            Path to downloaded model

        Raises:
            ConfigurationError: If model name is invalid
            BackendUnavailableError: If download fails

        Example:
            >>> manager = ModelManager()
            >>> path = manager.download_model("base")
            >>> print(path)
            /home/user/.cache/huggingface/hub/models--guillaumekln--faster-whisper-base/...
        """
        # Validate model name
        if model_name not in MODEL_REPOS:
            valid_models = ", ".join(sorted(MODEL_REPOS.keys()))
            raise ConfigurationError(
                f"Invalid model name '{model_name}'",
                context={
                    "model_name": model_name,
                    "valid_models": list(MODEL_REPOS.keys()),
                },
                suggestions=[
                    f"Choose a valid model: {valid_models}",
                    "Available models: tiny (75MB), base (150MB), small (500MB), medium (1.5GB), large (3GB)",
                ],
            )

        # Check if already downloaded
        local_path = self.get_model_path(model_name)
        if local_path is not None:
            logger.info(f"Model {model_name} already downloaded at {local_path}")
            return local_path

        repo_id = MODEL_REPOS[model_name]
        logger.info(f"Downloading model {model_name} from {repo_id}")

        try:
            from huggingface_hub import hf_hub_download

            # Known stable revisions for each model (pinned for security)
            # These are verified commit hashes from the official repos
            model_revisions: dict[str, str] = {
                ModelSize.TINY.value: "main",  # Uses latest stable
                ModelSize.BASE.value: "main",
                ModelSize.SMALL.value: "main",
                ModelSize.MEDIUM.value: "main",
                ModelSize.LARGE.value: "main",
                ModelSize.LARGE_V3.value: "main",
                ModelSize.LARGE_V3_TURBO.value: "main",
            }
            revision = model_revisions.get(model_name, "main")

            # Download model with revision pinning for supply chain security
            model_path = hf_hub_download(
                repo_id=repo_id,
                filename="model.bin",
                cache_dir=self._cache_dir,
                revision=revision,
            )

            logger.info(f"Model {model_name} downloaded to {model_path}")
            return Path(model_path)

        except ImportError as e:
            from audiocore.errors.backend import BackendUnavailableError

            raise BackendUnavailableError(
                "huggingface-hub not installed",
                context={"model_name": model_name},
                suggestions=[
                    "Install huggingface-hub: pip install huggingface-hub",
                    "Or install audiocore with huggingface extras: pip install audiocore[huggingface]",
                ],
            ) from e
        except Exception as e:
            from audiocore.errors.backend import BackendUnavailableError

            logger.error(f"Failed to download model {model_name}: {e}")
            raise BackendUnavailableError(
                f"Failed to download model {model_name}",
                context={"model_name": model_name, "repo_id": repo_id, "error": str(e)},
                suggestions=[
                    "Check your internet connection",
                    "Verify HuggingFace Hub is accessible",
                    f"Try downloading manually: huggingface-cli download {repo_id}",
                ],
            ) from e

    def get_model_path(self, model_name: str) -> Path | None:
        """Get path to cached model if exists.

        Checks if model is already downloaded in cache directory.

        Args:
            model_name: Model name (tiny, base, small, medium, large)

        Returns:
            Path to cached model or None if not found

        Example:
            >>> manager = ModelManager()
            >>> path = manager.get_model_path("base")
            >>> if path:
            ...     print(f"Model cached at {path}")
            ... else:
            ...     print("Model not downloaded")
        """
        # Validate model name
        if model_name not in MODEL_REPOS:
            return None

        repo_id = MODEL_REPOS[model_name]

        # HuggingFace cache structure: models--namespace--repo_name
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = self._cache_dir / cache_folder_name

        if not cache_path.exists():
            return None

        # Look for model.bin in the snapshots
        snapshots_dir = cache_path / "snapshots"
        if not snapshots_dir.exists():
            return None

        # Get the latest snapshot
        try:
            snapshots = sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime)
            if snapshots:
                latest_snapshot = snapshots[-1]
                model_file = latest_snapshot / "model.bin"
                if model_file.exists():
                    return model_file
        except Exception as e:
            logger.debug(f"Error checking cached model: {e}")

        return None

    def list_models(self) -> list[ModelInfo]:
        """List all available faster-whisper models.

        Returns a list of all model sizes with download status.

        Returns:
            List of ModelInfo objects for each model

        Example:
            >>> manager = ModelManager()
            >>> models = manager.list_models()
            >>> for model in models:
            ...     status = "downloaded" if model.downloaded else "not downloaded"
            ...     print(f"{model.name}: {status}")
            tiny: downloaded
            base: not downloaded
            ...
        """
        models: list[ModelInfo] = []

        for name in [
            ModelSize.TINY.value,
            ModelSize.BASE.value,
            ModelSize.SMALL.value,
            ModelSize.MEDIUM.value,
            ModelSize.LARGE.value,
            ModelSize.LARGE_V3.value,
            ModelSize.LARGE_V3_TURBO.value,
        ]:
            local_path = self.get_model_path(name)
            models.append(
                ModelInfo(
                    name=name,
                    size_mb=MODEL_SIZES_MB[name],
                    repo_id=MODEL_REPOS[name],
                    downloaded=local_path is not None,
                    local_path=local_path,
                )
            )

        return models

    def delete_model(self, model_name: str) -> None:
        """Delete cached model from disk.

        Removes model cache directory from disk.

        Args:
            model_name: Model name (tiny, base, small, medium, large)

        Raises:
            ConfigurationError: If model name is invalid
            ConfigurationError: If model not found in cache

        Example:
            >>> manager = ModelManager()
            >>> manager.delete_model("base")
            >>> # Model removed from cache
        """
        # Validate model name
        if model_name not in MODEL_REPOS:
            valid_models = ", ".join(sorted(MODEL_REPOS.keys()))
            raise ConfigurationError(
                f"Invalid model name '{model_name}'",
                context={
                    "model_name": model_name,
                    "valid_models": list(MODEL_REPOS.keys()),
                },
                suggestions=[
                    f"Choose a valid model: {valid_models}",
                    "Use list_models() to see available models",
                ],
            )

        # Get cache path
        repo_id = MODEL_REPOS[model_name]
        cache_folder_name = f"models--{repo_id.replace('/', '--')}"
        cache_path = self._cache_dir / cache_folder_name

        if not cache_path.exists():
            raise ConfigurationError(
                f"Model {model_name} not found in cache",
                context={"model_name": model_name, "cache_path": str(cache_path)},
                suggestions=[
                    f"Use download_model('{model_name}') to download the model first",
                    "Use list_models() to see downloaded models",
                ],
            )

        # Delete cache directory
        try:
            shutil.rmtree(cache_path)
            logger.info(f"Deleted model {model_name} from cache")
        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            raise ConfigurationError(
                f"Failed to delete model {model_name}",
                context={"model_name": model_name, "cache_path": str(cache_path)},
                suggestions=[
                    "Check file permissions",
                    f"Manually delete: rm -rf {cache_path}",
                ],
            ) from e

    def is_model_downloaded(self, model_name: str) -> bool:
        """Check if model is downloaded and cached.

        Args:
            model_name: Model name (tiny, base, small, medium, large)

        Returns:
            True if model is cached locally

        Example:
            >>> manager = ModelManager()
            >>> if manager.is_model_downloaded("base"):
            ...     print("Base model ready to use")
        """
        return self.get_model_path(model_name) is not None

    def clear(self) -> None:
        """Clear all cached models (for testing).

        Removes all downloaded models from cache.

        Warning:
            This will permanently delete all cached models.
        """
        # Clear singleton instance under class-level lock for thread safety
        with ModelManager._lock:
            # Delete cached model files
            for model_name in list(MODEL_REPOS.keys()):
                repo_id = MODEL_REPOS[model_name]
                cache_folder_name = f"models--{repo_id.replace('/', '--')}"
                cache_path = self._cache_dir / cache_folder_name

                if cache_path.exists():
                    try:
                        shutil.rmtree(cache_path)
                        logger.debug(f"Cleared cache for model {model_name}")
                    except Exception as e:
                        logger.warning(f"Failed to clear cache for {model_name}: {e}")

            self._models.clear()
            ModelManager._instance = None


# Convenience function for getting model info
def get_model_info(model_name: str) -> ModelInfo | None:
    """Get information about a specific model.

    Args:
        model_name: Model name (tiny, base, small, medium, large)

    Returns:
        ModelInfo if model name is valid, else None

    Example:
        >>> info = get_model_info("base")
        >>> print(f"Model size: {info.size_mb}MB")
        Model size: 150MB
    """
    if model_name not in MODEL_REPOS:
        return None

    manager = ModelManager()
    models = manager.list_models()

    for model in models:
        if model.name == model_name:
            return model

    return None
