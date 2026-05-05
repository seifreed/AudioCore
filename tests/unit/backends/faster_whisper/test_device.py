"""Unit tests for device detection utilities.

Tests GPU device detection, validation, and information gathering
with graceful handling when torch is not installed.
"""

import pytest

from audiocore.backends.faster_whisper.device import (
    DEVICE_CPU,
    DEVICE_CUDA,
    DEVICE_MPS,
    DeviceType,
    get_best_device,
    get_device_info,
    validate_device,
)


class TestDeviceConstants:
    """Test device type constants."""

    def test_device_cuda_constant(self) -> None:
        """DEVICE_CUDA should be 'cuda'."""
        assert DEVICE_CUDA == "cuda"

    def test_device_mps_constant(self) -> None:
        """DEVICE_MPS should be 'mps'."""
        assert DEVICE_MPS == "mps"

    def test_device_cpu_constant(self) -> None:
        """DEVICE_CPU should be 'cpu'."""
        assert DEVICE_CPU == "cpu"


class TestDeviceTypeEnum:
    """Test DeviceType enumeration."""

    def test_device_type_cuda(self) -> None:
        """DeviceType.CUDA should equal 'cuda'."""
        assert DeviceType.CUDA == "cuda"

    def test_device_type_mps(self) -> None:
        """DeviceType.MPS should equal 'mps'."""
        assert DeviceType.MPS == "mps"

    def test_device_type_cpu(self) -> None:
        """DeviceType.CPU should equal 'cpu'."""
        assert DeviceType.CPU == "cpu"

    def test_device_type_str_conversion(self) -> None:
        """DeviceType members should convert to string."""
        assert str(DeviceType.CUDA) == "cuda"
        assert str(DeviceType.MPS) == "mps"
        assert str(DeviceType.CPU) == "cpu"


class TestGetBestDevice:
    """Test get_best_device function."""

    def test_returns_string(self) -> None:
        """get_best_device should return a string."""
        device = get_best_device()
        assert isinstance(device, str)

    def test_returns_valid_device(self) -> None:
        """get_best_device should return cuda, mps, or cpu."""
        device = get_best_device()
        assert device in {DEVICE_CUDA, DEVICE_MPS, DEVICE_CPU}


class TestGetDeviceInfo:
    """Test get_device_info function."""

    def test_returns_dict(self) -> None:
        """get_device_info should return a dictionary."""
        info = get_device_info()
        assert isinstance(info, dict)

    def test_has_device_key(self) -> None:
        """get_device_info should have 'device' key."""
        info = get_device_info()
        assert "device" in info
        assert info["device"] in {DEVICE_CUDA, DEVICE_MPS, DEVICE_CPU}

    def test_has_cuda_available_key(self) -> None:
        """get_device_info should have 'cuda_available' key."""
        info = get_device_info()
        assert "cuda_available" in info
        assert isinstance(info["cuda_available"], bool)

    def test_has_mps_available_key(self) -> None:
        """get_device_info should have 'mps_available' key."""
        info = get_device_info()
        assert "mps_available" in info
        assert isinstance(info["mps_available"], bool)

    def test_has_torch_version_key(self) -> None:
        """get_device_info should have 'torch_version' key."""
        info = get_device_info()
        assert "torch_version" in info

    def test_has_cuda_version_key(self) -> None:
        """get_device_info should have 'cuda_version' key."""
        info = get_device_info()
        assert "cuda_version" in info

    def test_has_device_count_key(self) -> None:
        """get_device_info should have 'device_count' key."""
        info = get_device_info()
        assert "device_count" in info
        assert isinstance(info["device_count"], int)

    def test_has_device_name_key(self) -> None:
        """get_device_info should have 'device_name' key."""
        info = get_device_info()
        assert "device_name" in info

    def test_device_count_non_negative(self) -> None:
        """device_count should be >= 0."""
        info = get_device_info()
        assert info["device_count"] >= 0


class TestValidateDevice:
    """Test validate_device function."""

    def test_validate_cpu_always_returns_cpu(self) -> None:
        """validate_device('cpu') should always return 'cpu'."""
        device = validate_device("cpu")
        assert device == DEVICE_CPU

    def test_validates_case_insensitive(self) -> None:
        """validate_device should handle case-insensitive input."""
        device = validate_device("CUDA")
        assert device in {DEVICE_CUDA, DEVICE_MPS, DEVICE_CPU}

    def test_strips_surrounding_whitespace(self) -> None:
        """Regression: device values with incidental whitespace should parse."""
        device = validate_device(" cpu ")
        assert device == DEVICE_CPU

    def test_invalid_device_raises_error(self) -> None:
        """validate_device should raise ValueError for invalid device."""
        with pytest.raises(ValueError) as exc_info:
            validate_device("gpu")
        assert "Invalid device" in str(exc_info.value)
        assert "Valid options" in str(exc_info.value)

    def test_invalid_device_includes_suggestions(self) -> None:
        """validate_device error should include valid options."""
        with pytest.raises(ValueError) as exc_info:
            validate_device("invalid")
        error_msg = str(exc_info.value)
        assert "cuda" in error_msg
        assert "mps" in error_msg
        assert "cpu" in error_msg

    def test_cpu_lowercased(self) -> None:
        """validate_device should normalize 'CPU' to 'cpu'."""
        device = validate_device("CPU")
        assert device == DEVICE_CPU

    def test_validates_cuda_returns_cuda_or_fallback(self) -> None:
        """validate_device('cuda') returns cuda if available, else fallback."""
        device = validate_device("cuda")
        # Will be cuda, mps, or cpu depending on availability
        assert device in {DEVICE_CUDA, DEVICE_MPS, DEVICE_CPU}

    def test_validates_mps_returns_mps_or_fallback(self) -> None:
        """validate_device('mps') returns mps if available, else cpu."""
        device = validate_device("mps")
        # Will be mps or cpu depending on availability
        assert device in {DEVICE_MPS, DEVICE_CPU}


class TestDeviceDetectionConsistency:
    """Test consistency between device detection functions."""

    def test_get_best_device_matches_device_info(self) -> None:
        """get_best_device should match device_info['device']."""
        best = get_best_device()
        info = get_device_info()
        assert best == info["device"]

    def test_validate_cpu_always_consistent(self) -> None:
        """validate_device('cpu') should always return 'cpu'."""
        device = validate_device("cpu")
        assert device == DEVICE_CPU

    def test_cuda_available_matches_device_info(self) -> None:
        """CUDA availability should match between functions."""
        info = get_device_info()
        cuda_device = validate_device("cuda")

        if info["cuda_available"]:
            assert cuda_device == DEVICE_CUDA
        else:
            # Should fall back to MPS or CPU
            assert cuda_device in {DEVICE_MPS, DEVICE_CPU}

    def test_mps_available_matches_device_info(self) -> None:
        """MPS should always fall back to CPU since CTranslate2 doesn't support MPS."""
        mps_device = validate_device("mps")

        # CTranslate2 does not support MPS — validate_device should always return CPU
        assert mps_device == DEVICE_CPU


class TestDeviceStringNormalization:
    """Test device string normalization."""

    def test_cuda_lowercase_normalization(self) -> None:
        """validate_device should normalize CUDA to cuda."""
        assert validate_device("CUDA") in {DEVICE_CUDA, DEVICE_CPU}

    def test_mps_lowercase_normalization(self) -> None:
        """validate_device should normalize MPS to mps, falling back to CPU."""
        assert validate_device("MPS") == DEVICE_CPU

    def test_cpu_lowercase_normalization(self) -> None:
        """validate_device should normalize CPU to cpu."""
        assert validate_device("CPU") == DEVICE_CPU

    def test_mixed_case_normalization(self) -> None:
        """validate_device should handle mixed case."""
        assert validate_device("Cuda") in {DEVICE_CUDA, DEVICE_MPS, DEVICE_CPU}
        assert validate_device("MpS") in {DEVICE_MPS, DEVICE_CPU}
        assert validate_device("CpU") == DEVICE_CPU

    def test_whitespace_normalization(self) -> None:
        """Regression: normalization should strip surrounding whitespace."""
        assert validate_device("\tCPU\n") == DEVICE_CPU
