"""Faster-whisper backend package for AudioCore.

This package provides model management, device detection, and configuration
for the faster-whisper transcription backend.

Key Components:
    - ModelManager: Singleton for HuggingFace model download and caching
    - Device Detection: GPU device detection (CUDA, MPS, CPU)
    - FasterWhisperConfig: Configuration model for faster-whisper backend

Public API:
    ModelManager: Download and cache faster-whisper models
    ModelInfo: Model metadata information
    FasterWhisperConfig: Configuration for faster-whisper
    DeviceType: Device type enumeration
    get_best_device: Auto-detect best available device
    get_device_info: Get detailed device information
    validate_device: Validate device string with fallback

Example:
    >>> from audiocore.backends.faster_whisper import ModelManager, get_best_device
    >>> from audiocore.config.faster_whisper_config import FasterWhisperConfig

    >>> # Auto-detect device
    >>> device = get_best_device()
    >>> print(device)
    cuda

    >>> # Download model
    >>> manager = ModelManager()
    >>> path = manager.download_model("base")
    >>> print(path)
    /home/user/.cache/huggingface/hub/models--...

    >>> # Configure backend
    >>> config = FasterWhisperConfig(
    ...     model_size="base",
    ...     device=device,
    ...     beam_size=5,
    ... )
"""

from audiocore.backends.faster_whisper.device import (
    DEVICE_CPU,
    DEVICE_CUDA,
    DEVICE_MPS,
    DeviceType,
    get_best_device,
    get_device_info,
    validate_device,
)
from audiocore.backends.faster_whisper.model_manager import (
    MODEL_REPOS,
    MODEL_SIZES_MB,
    ModelInfo,
    ModelManager,
    get_model_info,
)
from audiocore.config.faster_whisper_config import (
    ComputeType,
    FasterWhisperConfig,
)

__all__ = [
    # Device detection
    "DEVICE_CPU",
    "DEVICE_CUDA",
    "DEVICE_MPS",
    "DeviceType",
    "get_best_device",
    "get_device_info",
    "validate_device",
    # Model management
    "MODEL_REPOS",
    "MODEL_SIZES_MB",
    "ModelInfo",
    "ModelManager",
    "get_model_info",
    # Configuration
    "ComputeType",
    "FasterWhisperConfig",
]
