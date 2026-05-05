"""Unit tests for FasterWhisperConfig configuration model.

Tests default values, validation, field coercion, and integration.
"""

import pytest
from pydantic import ValidationError

from audiocore.config.faster_whisper_config import (
    ComputeType,
    FasterWhisperConfig,
)
from audiocore.types.backend import ModelSize


class TestFasterWhisperConfigDefaults:
    """Test default values for all FasterWhisperConfig fields."""

    def test_default_model_size_is_base(self) -> None:
        """Default model_size should be BASE."""
        config = FasterWhisperConfig()
        assert config.model_size == ModelSize.BASE

    def test_default_device_is_none(self) -> None:
        """Default device should be None (auto-detect)."""
        config = FasterWhisperConfig()
        assert config.device is None

    def test_default_compute_type_is_default(self) -> None:
        """Default compute_type should be DEFAULT."""
        config = FasterWhisperConfig()
        assert config.compute_type == ComputeType.DEFAULT

    def test_default_language_is_none(self) -> None:
        """Default language should be None (auto-detect)."""
        config = FasterWhisperConfig()
        assert config.language is None

    def test_default_beam_size_is_5(self) -> None:
        """Default beam_size should be 5."""
        config = FasterWhisperConfig()
        assert config.beam_size == 5

    def test_default_best_of_is_5(self) -> None:
        """Default best_of should be 5."""
        config = FasterWhisperConfig()
        assert config.best_of == 5

    def test_default_patience_is_1(self) -> None:
        """Default patience should be 1.0."""
        config = FasterWhisperConfig()
        assert config.patience == 1.0

    def test_default_temperature_is_0(self) -> None:
        """Default temperature should be 0.0."""
        config = FasterWhisperConfig()
        assert config.temperature == 0.0

    def test_default_compression_ratio_threshold_is_2_4(self) -> None:
        """Default compression_ratio_threshold should be 2.4."""
        config = FasterWhisperConfig()
        assert config.compression_ratio_threshold == 2.4

    def test_default_log_prob_threshold_is_minus_1(self) -> None:
        """Default log_prob_threshold should be -1.0."""
        config = FasterWhisperConfig()
        assert config.log_prob_threshold == -1.0

    def test_default_no_speech_threshold_is_0_6(self) -> None:
        """Default no_speech_threshold should be 0.6."""
        config = FasterWhisperConfig()
        assert config.no_speech_threshold == 0.6

    def test_default_condition_on_previous_text_is_true(self) -> None:
        """Default condition_on_previous_text should be True."""
        config = FasterWhisperConfig()
        assert config.condition_on_previous_text is True

    def test_default_initial_prompt_is_none(self) -> None:
        """Default initial_prompt should be None."""
        config = FasterWhisperConfig()
        assert config.initial_prompt is None

    def test_default_word_timestamps_is_true(self) -> None:
        """Default word_timestamps should be True."""
        config = FasterWhisperConfig()
        assert config.word_timestamps is True

    def test_default_vad_filter_is_true(self) -> None:
        """Default vad_filter should be True."""
        config = FasterWhisperConfig()
        assert config.vad_filter is True


class TestFasterWhisperConfigDeviceValidation:
    """Test device field validation."""

    def test_valid_device_cuda(self) -> None:
        """Should accept 'cuda' device."""
        config = FasterWhisperConfig(device="cuda")
        assert config.device == "cuda"

    def test_valid_device_mps(self) -> None:
        """Should accept 'mps' device."""
        config = FasterWhisperConfig(device="mps")
        assert config.device == "mps"

    def test_valid_device_cpu(self) -> None:
        """Should accept 'cpu' device."""
        config = FasterWhisperConfig(device="cpu")
        assert config.device == "cpu"

    def test_valid_device_none(self) -> None:
        """Should accept None device (auto-detect)."""
        config = FasterWhisperConfig(device=None)
        assert config.device is None

    def test_device_is_case_insensitive(self) -> None:
        """Should normalize device to lowercase."""
        config = FasterWhisperConfig(device="CUDA")
        assert config.device == "cuda"

    def test_device_strips_surrounding_whitespace(self) -> None:
        """Regression: device config should tolerate incidental whitespace."""
        config = FasterWhisperConfig(device=" cuda ")
        assert config.device == "cuda"

    def test_invalid_device_raises_error(self) -> None:
        """Should raise ValidationError for invalid device."""
        with pytest.raises(ValidationError) as exc_info:
            FasterWhisperConfig(device="gpu")
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Invalid device" in str(errors[0]["ctx"]["error"])

    def test_device_validation_message(self) -> None:
        """Should provide helpful validation message."""
        with pytest.raises(ValidationError) as exc_info:
            FasterWhisperConfig(device="invalid")
        assert "Valid options:" in str(exc_info.value)


class TestFasterWhisperConfigComputeTypeValidation:
    """Test compute_type field validation."""

    def test_valid_compute_type_default(self) -> None:
        """Should accept DEFAULT compute type."""
        config = FasterWhisperConfig(compute_type="default")
        assert config.compute_type == ComputeType.DEFAULT

    def test_valid_compute_type_int8(self) -> None:
        """Should accept INT8 compute type."""
        config = FasterWhisperConfig(compute_type="int8")
        assert config.compute_type == ComputeType.INT8

    def test_valid_compute_type_float16(self) -> None:
        """Should accept FLOAT16 compute type."""
        config = FasterWhisperConfig(compute_type="float16")
        assert config.compute_type == ComputeType.FLOAT16

    def test_valid_compute_type_float32(self) -> None:
        """Regression: documented CTranslate2 float32 compute type should be accepted."""
        config = FasterWhisperConfig(compute_type="float32")
        assert config.compute_type == ComputeType.FLOAT32

    def test_valid_compute_type_int8_float16(self) -> None:
        """Should accept INT8_FLOAT16 compute type."""
        config = FasterWhisperConfig(compute_type="int8_float16")
        assert config.compute_type == ComputeType.INT8_FLOAT16

    def test_compute_type_strips_surrounding_whitespace(self) -> None:
        """Regression: compute_type config should tolerate incidental whitespace."""
        config = FasterWhisperConfig(compute_type=" int8-float16 ")
        assert config.compute_type == ComputeType.INT8_FLOAT16

    def test_invalid_compute_type_raises_error(self) -> None:
        """Should raise ValidationError for invalid compute type."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(compute_type="half")


class TestFasterWhisperConfigLanguageValidation:
    """Test language field validation."""

    def test_valid_language_two_letter(self) -> None:
        """Should accept 2-letter language codes."""
        config = FasterWhisperConfig(language="en")
        assert config.language == "en"

    def test_valid_language_three_letter(self) -> None:
        """Should accept 3-letter language codes."""
        config = FasterWhisperConfig(language="spa")
        assert config.language == "spa"

    def test_language_is_normalized_to_lowercase(self) -> None:
        """Should normalize language to lowercase."""
        config = FasterWhisperConfig(language="EN")
        assert config.language == "en"

    def test_language_strips_surrounding_whitespace(self) -> None:
        """Regression: language config should tolerate incidental whitespace."""
        config = FasterWhisperConfig(language=" en-US ")
        assert config.language == "en-us"

    def test_invalid_language_single_letter_raises_error(self) -> None:
        """Should raise ValidationError for single-letter language codes."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(language="e")

    def test_invalid_language_long_raises_error(self) -> None:
        """Should raise ValidationError for long language codes."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(language="english")


class TestFasterWhisperConfigBeamValidation:
    """Test beam_size and best_of validation."""

    def test_valid_beam_size(self) -> None:
        """Should accept valid beam_size."""
        config = FasterWhisperConfig(beam_size=10, best_of=10)
        assert config.beam_size == 10

    def test_beam_size_min_value(self) -> None:
        """Should accept minimum beam_size of 1."""
        config = FasterWhisperConfig(beam_size=1)
        assert config.beam_size == 1

    def test_beam_size_max_value(self) -> None:
        """Should accept maximum beam_size of 20."""
        config = FasterWhisperConfig(beam_size=20, best_of=20)
        assert config.beam_size == 20

    def test_beam_size_below_min_raises_error(self) -> None:
        """Should raise ValidationError for beam_size < 1."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(beam_size=0)

    def test_beam_size_above_max_raises_error(self) -> None:
        """Should raise ValidationError for beam_size > 20."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(beam_size=21)

    def test_best_of_equal_to_beam_size(self) -> None:
        """Should accept best_of equal to beam_size."""
        config = FasterWhisperConfig(beam_size=5, best_of=5)
        assert config.best_of == 5

    def test_best_of_greater_than_beam_size(self) -> None:
        """Should accept best_of > beam_size."""
        config = FasterWhisperConfig(beam_size=5, best_of=10)
        assert config.best_of == 10

    def test_best_of_less_than_beam_size_raises_error(self) -> None:
        """Should raise ValidationError when best_of < beam_size."""
        with pytest.raises(ValidationError) as exc_info:
            FasterWhisperConfig(beam_size=5, best_of=3)
        assert "best_of" in str(exc_info.value).lower()

    def test_best_of_min_value(self) -> None:
        """Should accept minimum best_of of 1."""
        config = FasterWhisperConfig(beam_size=1, best_of=1)
        assert config.best_of == 1


class TestFasterWhisperConfigTemperatureValidation:
    """Test temperature validation."""

    def test_valid_temperature_0(self) -> None:
        """Should accept temperature 0.0."""
        config = FasterWhisperConfig(temperature=0.0)
        assert config.temperature == 0.0

    def test_valid_temperature_1(self) -> None:
        """Should accept temperature 1.0."""
        config = FasterWhisperConfig(temperature=1.0)
        assert config.temperature == 1.0

    def test_valid_temperature_midpoint(self) -> None:
        """Should accept temperature 0.5."""
        config = FasterWhisperConfig(temperature=0.5)
        assert config.temperature == 0.5

    def test_temperature_below_min_raises_error(self) -> None:
        """Should raise ValidationError for temperature < 0.0."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(temperature=-0.1)

    def test_temperature_above_max_raises_error(self) -> None:
        """Should raise ValidationError for temperature > 1.0."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(temperature=1.1)


class TestFasterWhisperConfigThresholdValidation:
    """Test threshold validation."""

    def test_valid_compression_ratio_threshold(self) -> None:
        """Should accept valid compression_ratio_threshold."""
        config = FasterWhisperConfig(compression_ratio_threshold=3.0)
        assert config.compression_ratio_threshold == 3.0

    def test_compression_ratio_threshold_valid_range(self) -> None:
        """Should accept compression_ratio_threshold in [1.0, 10.0]."""
        config = FasterWhisperConfig(compression_ratio_threshold=10.0)
        assert config.compression_ratio_threshold == 10.0

    def test_compression_ratio_threshold_below_min_raises_error(
        self,
    ) -> None:
        """Should raise ValidationError for value < 1.0."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(compression_ratio_threshold=0.5)

    def test_valid_log_prob_threshold(self) -> None:
        """Should accept valid log_prob_threshold."""
        config = FasterWhisperConfig(log_prob_threshold=-0.5)
        assert config.log_prob_threshold == -0.5

    def test_log_prob_threshold_valid_range(self) -> None:
        """Should accept log_prob_threshold in [-5.0, 0.0]."""
        config = FasterWhisperConfig(log_prob_threshold=-5.0)
        assert config.log_prob_threshold == -5.0

    def test_log_prob_threshold_above_max_raises_error(self) -> None:
        """Should raise ValidationError for value > 0.0."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(log_prob_threshold=0.1)

    def test_valid_no_speech_threshold(self) -> None:
        """Should accept valid no_speech_threshold."""
        config = FasterWhisperConfig(no_speech_threshold=0.5)
        assert config.no_speech_threshold == 0.5

    def test_no_speech_threshold_valid_range(self) -> None:
        """Should accept no_speech_threshold in [0.0, 1.0]."""
        config = FasterWhisperConfig(no_speech_threshold=1.0)
        assert config.no_speech_threshold == 1.0

    def test_no_speech_threshold_out_of_range_raises_error(self) -> None:
        """Should raise ValidationError for value outside [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(no_speech_threshold=1.5)


class TestFasterWhisperConfigModelSize:
    """Test model_size field."""

    def test_model_size_accepts_enum(self) -> None:
        """Should accept ModelSize enum."""
        config = FasterWhisperConfig(model_size=ModelSize.LARGE)
        assert config.model_size == ModelSize.LARGE

    def test_model_size_accepts_string(self) -> None:
        """Should accept string model_size and coerce to enum."""
        config = FasterWhisperConfig(model_size="small")  # type: ignore[arg-type]
        assert config.model_size == ModelSize.SMALL

    def test_model_size_invalid_raises_error(self) -> None:
        """Should raise ValidationError for invalid model_size."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(model_size="extra_large")  # type: ignore[arg-type]

    def test_get_available_models(self) -> None:
        """Should return list of available models."""
        models = FasterWhisperConfig.get_available_models()
        assert "tiny" in models
        assert "base" in models
        assert "small" in models
        assert "medium" in models
        assert "large" in models

    def test_model_name_property(self) -> None:
        """model_name property should return model size value."""
        config = FasterWhisperConfig(model_size=ModelSize.BASE)
        assert config.model_name == "base"


class TestFasterWhisperConfigExtraFields:
    """Test that extra fields are forbidden."""

    def test_extra_fields_forbidden(self) -> None:
        """Should raise ValidationError for extra fields."""
        with pytest.raises(ValidationError):
            FasterWhisperConfig(unknown_field="value")  # type: ignore[call-arg]


class TestFasterWhisperConfigAllFields:
    """Test configuration with all fields set."""

    def test_all_fields_set(self) -> None:
        """Should accept all fields set."""
        config = FasterWhisperConfig(
            model_size=ModelSize.LARGE,
            device="cuda",
            compute_type=ComputeType.FLOAT16,
            language="en",
            beam_size=10,
            best_of=15,
            patience=1.5,
            temperature=0.2,
            compression_ratio_threshold=2.5,
            log_prob_threshold=-0.5,
            no_speech_threshold=0.5,
            condition_on_previous_text=False,
            initial_prompt="This is a test.",
            word_timestamps=False,
            vad_filter=False,
        )
        assert config.model_size == ModelSize.LARGE
        assert config.device == "cuda"
        assert config.compute_type == ComputeType.FLOAT16
        assert config.language == "en"
        assert config.beam_size == 10
        assert config.best_of == 15
        assert config.patience == 1.5
        assert config.temperature == 0.2
        assert config.compression_ratio_threshold == 2.5
        assert config.log_prob_threshold == -0.5
        assert config.no_speech_threshold == 0.5
        assert config.condition_on_previous_text is False
        assert config.initial_prompt == "This is a test."
        assert config.word_timestamps is False
        assert config.vad_filter is False

    def test_model_dump(self) -> None:
        """Should serialize to dict correctly."""
        config = FasterWhisperConfig(
            model_size=ModelSize.SMALL,
            device="cpu",
            beam_size=5,
        )
        data = config.model_dump()
        assert data["model_size"] == ModelSize.SMALL
        assert data["device"] == "cpu"
        assert data["beam_size"] == 5


class TestFasterWhisperConfigBooleanFields:
    """Test boolean field defaults."""

    def test_condition_on_previous_text_false(self) -> None:
        """Should accept condition_on_previous_text=False."""
        config = FasterWhisperConfig(condition_on_previous_text=False)
        assert config.condition_on_previous_text is False

    def test_word_timestamps_false(self) -> None:
        """Should accept word_timestamps=False."""
        config = FasterWhisperConfig(word_timestamps=False)
        assert config.word_timestamps is False

    def test_vad_filter_false(self) -> None:
        """Should accept vad_filter=False."""
        config = FasterWhisperConfig(vad_filter=False)
        assert config.vad_filter is False
