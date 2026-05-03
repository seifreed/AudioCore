"""Device detection utilities for faster-whisper backend.

This module provides utilities for detecting and validating GPU devices
available for faster-whisper inference. It supports CUDA, MPS (Apple Silicon),
and CPU devices with graceful fallback when dependencies are unavailable.

Key Functions:
    - get_best_device(): Auto-detect best available device
    - get_device_info(): Get detailed device information
    - validate_device(): Validate and get fallback for device string

Example:
    >>> from audiocore.backends.faster_whisper.device import get_best_device
    >>> device = get_best_device()
    >>> print(device)  # 'cuda', 'mps', or 'cpu'
    cuda
"""

import contextlib
import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Device type constants
DEVICE_CUDA = "cuda"
DEVICE_MPS = "mps"
DEVICE_CPU = "cpu"


def get_best_device() -> str:
    """Auto-detect best available device for inference.

    Priority: CUDA > MPS > CPU

    Detection logic:
        1. Check if torch is installed
        2. Check CUDA availability
        3. Check MPS (Apple Silicon) availability
        4. Fall back to CPU

    Returns:
        Device string: "cuda", "mps", or "cpu"

    Example:
        >>> device = get_best_device()
        >>> print(device)
        cuda  # or 'mps' or 'cpu'
    """
    try:
        import torch

        # Check CUDA (NVIDIA GPU)
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            if device_count > 0:
                device_name_gpu = torch.cuda.get_device_name(0)
                logger.debug(f"CUDA available: {device_count} device(s), using {device_name_gpu}")
            return DEVICE_CUDA

        # Check MPS (Apple Silicon)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.debug("MPS (Apple Silicon) available")
            return DEVICE_MPS

    except ImportError:
        logger.debug("torch not installed, falling back to CPU")
    except Exception as e:
        logger.warning(f"Error detecting device: {e}, falling back to CPU")

    logger.debug("No GPU detected, using CPU")
    return DEVICE_CPU


def get_device_info() -> dict[str, Any]:
    """Get detailed information about available devices.

    Returns:
        Dictionary with device information:
            - device: str (selected device: "cuda", "mps", or "cpu")
            - cuda_available: bool
            - mps_available: bool
            - torch_version: str | None
            - cuda_version: str | None (if CUDA available)
            - device_count: int (GPU count, 0 if no GPU)
            - device_name: str | None (GPU name if available)

    Example:
        >>> info = get_device_info()
        >>> print(info['device'])
        'cuda'
        >>> print(info['cuda_version'])
        '12.1'
    """
    info: dict[str, Any] = {
        "device": DEVICE_CPU,
        "cuda_available": False,
        "mps_available": False,
        "torch_version": None,
        "cuda_version": None,
        "device_count": 0,
        "device_name": None,
    }

    try:
        import torch

        info["torch_version"] = torch.__version__

        # Check CUDA
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["device"] = DEVICE_CUDA
            info["device_count"] = torch.cuda.device_count()
            if info["device_count"] > 0:
                info["device_name"] = torch.cuda.get_device_name(0)
                # Try to get CUDA version
                with contextlib.suppress(AttributeError):
                    info["cuda_version"] = torch.version.cuda
            return info

        # Check MPS
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["mps_available"] = True
            info["device"] = DEVICE_MPS
            return info

    except ImportError:
        logger.debug("torch not installed")
    except Exception as e:
        logger.warning(f"Error getting device info: {e}")

    return info


def validate_device(device: str) -> str:
    """Validate device string and return available device.

    If requested device is not available, falls back to CPU with a warning.

    Args:
        device: Device string ("cuda", "mps", or "cpu")

    Returns:
        Validated device string (may be "cpu" if fallback applied)

    Raises:
        ValueError: If device string is invalid

    Example:
        >>> device = validate_device("cuda")
        >>> print(device)  # 'cuda' if available, else 'cpu'
        cuda
        >>> validate_device("invalid")
        # Raises ValueError
    """
    # Normalize device string
    device_lower = device.lower()

    # Validate device string
    valid_devices = {DEVICE_CUDA, DEVICE_MPS, DEVICE_CPU}
    if device_lower not in valid_devices:
        raise ValueError(
            f"Invalid device '{device}'. Valid options: {', '.join(sorted(valid_devices))}"
        )

    # CPU is always available
    if device_lower == DEVICE_CPU:
        return DEVICE_CPU

    # Check GPU availability
    device_info = get_device_info()

    # Check for CUDA
    if device_lower == DEVICE_CUDA:
        if device_info["cuda_available"]:
            logger.info(f"Using CUDA device: {device_info.get('device_name', 'unknown')}")
            return DEVICE_CUDA
        # Fall back to CPU (not MPS — CTranslate2 doesn't support MPS)
        logger.warning(
            f"CUDA requested but not available, falling back to CPU. "
            f"CUDA available: {device_info['cuda_available']}"
        )
        return DEVICE_CPU

    # Check for MPS
    if device_lower == DEVICE_MPS:
        if device_info["mps_available"]:
            logger.info("Using MPS device (Apple Silicon)")
            return DEVICE_MPS
        # Fall back to CPU
        logger.warning(
            f"MPS requested but not available, falling back to CPU. "
            f"MPS available: {device_info['mps_available']}"
        )
        return DEVICE_CPU

    # Should not reach here
    return DEVICE_CPU


class DeviceType(StrEnum):
    """Device type enumeration for type hints.

    This enum provides type-safe device constants.

    Attributes:
        CUDA: NVIDIA GPU device
        MPS: Apple Silicon GPU device
        CPU: CPU device
    """

    CUDA = DEVICE_CUDA
    MPS = DEVICE_MPS
    CPU = DEVICE_CPU
