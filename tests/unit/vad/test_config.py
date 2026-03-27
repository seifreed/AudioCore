"""Unit tests for VADConfig validation and integration.

Tests cover:
1. Default values
2. Field validation (min/max ranges)
3. Cross-field validation (thresholds and durations)
4. AppConfig integration
5. Environment variable loading
6. Strict mode (rejects unknown fields and wrong types)
"""

import os

import pytest
from pydantic import ValidationError

from audiocore.config import AppConfig, VADConfig


class TestVADConfigDefaults:
    """Test default values for VADConfig."""

    def test_vad_config_defaults_match_expected(self) -> None:
        """Test that all default values match expected values."""
        config = VADConfig()

        assert config.min_segment_duration == 0.5
        assert config.max_segment_duration == 30.0
        assert config.speech_threshold == 0.5
        assert config.silence_threshold == 0.3
        assert config.speech_pad_ms == 30
        assert config.min_silence_duration_ms == 100
        assert config.window_size_samples == 512

    def test_vad_config_all_fields_present(self) -> None:
        """Test that all expected fields are present."""
        config = VADConfig()

        assert hasattr(config, "min_segment_duration")
        assert hasattr(config, "max_segment_duration")
        assert hasattr(config, "speech_threshold")
        assert hasattr(config, "silence_threshold")
        assert hasattr(config, "speech_pad_ms")
        assert hasattr(config, "min_silence_duration_ms")
        assert hasattr(config, "window_size_samples")


class TestVADConfigFieldValidation:
    """Test field validation for VADConfig."""

    def test_min_segment_duration_minimum_value(self) -> None:
        """Test min_segment_duration minimum value (0.1)."""
        config = VADConfig(min_segment_duration=0.1)
        assert config.min_segment_duration == 0.1

    def test_min_segment_duration_maximum_value(self) -> None:
        """Test min_segment_duration maximum value (10.0)."""
        config = VADConfig(min_segment_duration=10.0)
        assert config.min_segment_duration == 10.0

    def test_min_segment_duration_rejects_invalid(self) -> None:
        """Test min_segment_duration rejects values outside range."""
        # Below minimum
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(min_segment_duration=0.05)
        assert "greater than or equal to 0.1" in str(exc_info.value)

        # Above maximum
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(min_segment_duration=15.0)
        assert "less than or equal to 10" in str(exc_info.value)

    def test_max_segment_duration_minimum_value(self) -> None:
        """Test max_segment_duration minimum value (5.0)."""
        config = VADConfig(max_segment_duration=5.0)
        assert config.max_segment_duration == 5.0

    def test_max_segment_duration_maximum_value(self) -> None:
        """Test max_segment_duration maximum value (300.0)."""
        config = VADConfig(max_segment_duration=300.0)
        assert config.max_segment_duration == 300.0

    def test_speech_threshold_range(self) -> None:
        """Test speech_threshold accepts valid range (0.0-1.0)."""
        # Minimum (with valid silence_threshold)
        config = VADConfig(speech_threshold=0.01, silence_threshold=0.0)
        assert config.speech_threshold == 0.01

        # Maximum
        config = VADConfig(speech_threshold=1.0, silence_threshold=0.5)
        assert config.speech_threshold == 1.0

        # Middle value
        config = VADConfig(speech_threshold=0.75, silence_threshold=0.5)
        assert config.speech_threshold == 0.75

    def test_silence_threshold_range(self) -> None:
        """Test silence_threshold accepts valid range (0.0-1.0)."""
        # Minimum
        config = VADConfig(silence_threshold=0.0)
        assert config.silence_threshold == 0.0

        # Middle value (with valid speech_threshold)
        config = VADConfig(silence_threshold=0.5, speech_threshold=0.6)
        assert config.silence_threshold == 0.5

        # Maximum (need speech_threshold > silence_threshold)
        config = VADConfig(silence_threshold=0.99, speech_threshold=1.0)
        assert config.silence_threshold == 0.99

    def test_speech_pad_ms_range(self) -> None:
        """Test speech_pad_ms accepts valid range (0-500)."""
        config = VADConfig(speech_pad_ms=0)
        assert config.speech_pad_ms == 0

        config = VADConfig(speech_pad_ms=500)
        assert config.speech_pad_ms == 500

        config = VADConfig(speech_pad_ms=100)
        assert config.speech_pad_ms == 100

    def test_min_silence_duration_ms_range(self) -> None:
        """Test min_silence_duration_ms accepts valid range (50-1000)."""
        config = VADConfig(min_silence_duration_ms=50)
        assert config.min_silence_duration_ms == 50

        config = VADConfig(min_silence_duration_ms=1000)
        assert config.min_silence_duration_ms == 1000

        config = VADConfig(min_silence_duration_ms=200)
        assert config.min_silence_duration_ms == 200

    def test_window_size_samples_one_of_valid_values(self) -> None:
        """Test window_size_samples accepts values in valid range (256-1024)."""
        config = VADConfig(window_size_samples=256)
        assert config.window_size_samples == 256

        config = VADConfig(window_size_samples=512)
        assert config.window_size_samples == 512

        config = VADConfig(window_size_samples=768)
        assert config.window_size_samples == 768

        config = VADConfig(window_size_samples=1024)
        assert config.window_size_samples == 1024

    def test_window_size_samples_rejects_invalid(self) -> None:
        """Test window_size_samples rejects values outside range."""
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(window_size_samples=128)
        assert "greater than or equal to 256" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            VADConfig(window_size_samples=2048)
        assert "less than or equal to 1024" in str(exc_info.value)


class TestVADConfigCrossFieldValidation:
    """Test cross-field validation for VADConfig."""

    def test_speech_threshold_must_be_greater_than_silence_threshold(self) -> None:
        """Test that speech_threshold > silence_threshold."""
        config = VADConfig(speech_threshold=0.7, silence_threshold=0.3)
        assert config.speech_threshold > config.silence_threshold

    def test_equal_thresholds_raises_validation_error(self) -> None:
        """Test that speech_threshold == silence_threshold raises error."""
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(speech_threshold=0.5, silence_threshold=0.5)
        assert "must be greater than" in str(exc_info.value)

    def test_min_segment_duration_must_be_less_than_max(self) -> None:
        """Test that min_segment_duration < max_segment_duration."""
        config = VADConfig(min_segment_duration=1.0, max_segment_duration=30.0)
        assert config.min_segment_duration < config.max_segment_duration

    def test_equal_duration_raises_validation_error(self) -> None:
        """Test that min == max raises error."""
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(min_segment_duration=10.0, max_segment_duration=10.0)
        assert "must be less than" in str(exc_info.value)

    def test_min_greater_than_max_raises_validation_error(self) -> None:
        """Test that min > max raises error."""
        # Use values within individual field ranges but invalid relationship
        # min_segment_duration: ge=0.1, le=10.0
        # max_segment_duration: ge=5.0, le=300.0
        # So min=8.0, max=6.0 passes field validation but fails cross-field
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(min_segment_duration=8.0, max_segment_duration=6.0)
        assert "must be less than" in str(exc_info.value)


class TestAppConfigIntegration:
    """Test AppConfig integration with VADConfig."""

    def test_app_config_has_vad_field(self) -> None:
        """Test that AppConfig has vad field."""
        config = AppConfig()
        assert hasattr(config, "vad")

    def test_app_config_uses_vad_defaults(self) -> None:
        """Test that AppConfig uses VADConfig defaults."""
        config = AppConfig()
        assert isinstance(config.vad, VADConfig)
        assert config.vad.min_segment_duration == 0.5
        assert config.vad.max_segment_duration == 30.0
        assert config.vad.speech_threshold == 0.5
        assert config.vad.silence_threshold == 0.3

    def test_app_config_accepts_vad_config(self) -> None:
        """Test that AppConfig accepts explicit VADConfig."""
        vad_config = VADConfig(
            min_segment_duration=2.0,
            max_segment_duration=60.0,
            speech_threshold=0.6,
            silence_threshold=0.2,
        )
        config = AppConfig(vad=vad_config)
        assert config.vad.min_segment_duration == 2.0
        assert config.vad.max_segment_duration == 60.0
        assert config.vad.speech_threshold == 0.6
        assert config.vad.silence_threshold == 0.2


class TestVADConfigEnvironmentVariables:
    """Test environment variable loading for VADConfig."""

    def test_vad_config_from_env_min_segment_duration(self) -> None:
        """Test loading min_segment_duration from env var."""
        os.environ["AUDIOCORE_VAD__MIN_SEGMENT_DURATION"] = "1.5"
        try:
            config = AppConfig()
            assert config.vad.min_segment_duration == 1.5
        finally:
            del os.environ["AUDIOCORE_VAD__MIN_SEGMENT_DURATION"]

    def test_vad_config_from_env_max_segment_duration(self) -> None:
        """Test loading max_segment_duration from env var."""
        os.environ["AUDIOCORE_VAD__MAX_SEGMENT_DURATION"] = "45.0"
        try:
            config = AppConfig()
            assert config.vad.max_segment_duration == 45.0
        finally:
            del os.environ["AUDIOCORE_VAD__MAX_SEGMENT_DURATION"]

    def test_vad_config_from_env_speech_threshold(self) -> None:
        """Test loading speech_threshold from env var."""
        os.environ["AUDIOCORE_VAD__SPEECH_THRESHOLD"] = "0.75"
        try:
            config = AppConfig()
            assert config.vad.speech_threshold == 0.75
        finally:
            del os.environ["AUDIOCORE_VAD__SPEECH_THRESHOLD"]

    def test_vad_config_from_multiple_env_vars(self) -> None:
        """Test loading multiple VAD config from env vars."""
        env_vars = {
            "AUDIOCORE_VAD__MIN_SEGMENT_DURATION": "2.0",
            "AUDIOCORE_VAD__MAX_SEGMENT_DURATION": "90.0",
            "AUDIOCORE_VAD__SPEECH_THRESHOLD": "0.6",
            "AUDIOCORE_VAD__SILENCE_THRESHOLD": "0.2",
            "AUDIOCORE_VAD__SPEECH_PAD_MS": "50",
            "AUDIOCORE_VAD__MIN_SILENCE_DURATION_MS": "150",
            "AUDIOCORE_VAD__WINDOW_SIZE_SAMPLES": "768",
        }
        for key, value in env_vars.items():
            os.environ[key] = value
        try:
            config = AppConfig()
            assert config.vad.min_segment_duration == 2.0
            assert config.vad.max_segment_duration == 90.0
            assert config.vad.speech_threshold == 0.6
            assert config.vad.silence_threshold == 0.2
            assert config.vad.speech_pad_ms == 50
            assert config.vad.min_silence_duration_ms == 150
            assert config.vad.window_size_samples == 768
        finally:
            for key in env_vars:
                del os.environ[key]


class TestVADConfigStrictMode:
    """Test VADConfig strict mode behavior."""

    def test_vad_config_rejects_unknown_fields(self) -> None:
        """Test that VADConfig rejects unknown fields."""
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(unknown_field="value")  # type: ignore[arg-type]
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_vad_config_rejects_wrong_types(self) -> None:
        """Test that VADConfig rejects wrong types but coerces strings."""
        # Strings should be coerced to floats
        config = VADConfig(min_segment_duration="1.5", max_segment_duration="30.0")
        assert config.min_segment_duration == 1.5
        assert config.max_segment_duration == 30.0

        # Strings should be coerced to ints
        config2 = VADConfig(speech_pad_ms="100")
        assert config2.speech_pad_ms == 100

    def test_vad_config_accepts_int_for_float_fields(self) -> None:
        """Test that VADConfig accepts int for float fields."""
        config = VADConfig(min_segment_duration=1, max_segment_duration=30)
        assert config.min_segment_duration == 1.0
        assert config.max_segment_duration == 30.0

    def test_vad_config_rejects_none_for_required_fields(self) -> None:
        """Test that VADConfig rejects None for required fields."""
        with pytest.raises(ValidationError) as exc_info:
            VADConfig(min_segment_duration=None)  # type: ignore[arg-type]
        assert (
            "none is not an allowed value" in str(exc_info.value).lower()
            or "input should be a valid number" in str(exc_info.value).lower()
        )


class TestVADConfigModelCopy:
    """Test VADConfig copy and update behavior."""

    def test_vad_config_model_copy(self) -> None:
        """Test that VADConfig can be copied with updates."""
        config = VADConfig()
        new_config = config.model_copy(update={"min_segment_duration": 2.0})
        assert new_config.min_segment_duration == 2.0
        assert config.min_segment_duration == 0.5  # Original unchanged

    def test_vad_config_with_valid_threshold_order(self) -> None:
        """Test VADConfig with valid threshold order."""
        config = VADConfig(speech_threshold=0.8, silence_threshold=0.2)
        assert config.speech_threshold == 0.8
        assert config.silence_threshold == 0.2

    def test_vad_config_with_edge_case_duration_values(self) -> None:
        """Test VADConfig with edge case duration values."""
        # Minimum valid difference (within min_segment_duration range)
        config = VADConfig(min_segment_duration=5.0, max_segment_duration=5.01)
        assert config.min_segment_duration == 5.0
        assert config.max_segment_duration == 5.01
