"""Unit tests for AppConfig settings model.

Tests environment variable loading, default values, enum coercion,
and SecretStr masking for secure API key handling.
"""

import pytest
from pydantic import SecretStr, ValidationError

from audiocore.config.openai_config import OpenAIConfig
from audiocore.config.settings import AppConfig
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class TestAppConfigDefaults:
    """Test default values for all AppConfig fields."""

    def test_default_backend(self) -> None:
        """Default backend should be AUTO."""
        config = AppConfig()
        assert config.backend == BackendType.AUTO

    def test_default_model_size(self) -> None:
        """Default model size should be BASE."""
        config = AppConfig()
        assert config.model_size == ModelSize.BASE

    def test_default_language(self) -> None:
        """Default language should be None."""
        config = AppConfig()
        assert config.language is None

    def test_default_output_format(self) -> None:
        """Default output format should be TEXT."""
        config = AppConfig()
        assert config.output_format == OutputFormat.TEXT

    def test_default_backend_preference(self) -> None:
        """Default backend preference should be AUTO."""
        config = AppConfig()
        assert config.backend_preference == SelectionPolicy.AUTO

    def test_default_api_key_none(self) -> None:
        """Default API key should be None (no key configured)."""
        config = AppConfig()
        assert config.openai_api_key is None


class TestEnvironmentVariableLoading:
    """Test environment variable loading with AUDIOCORE_ prefix."""

    def test_env_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUDIOCORE_BACKEND should load as BackendType enum."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")
        config = AppConfig()
        assert config.backend == BackendType.OPENAI

    def test_env_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUDIOCORE_MODEL should load as ModelSize enum."""
        monkeypatch.setenv("AUDIOCORE_MODEL", "large")
        config = AppConfig()
        assert config.model_size == ModelSize.LARGE

    def test_env_language(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUDIOCORE_LANGUAGE should load as string."""
        monkeypatch.setenv("AUDIOCORE_LANGUAGE", "es")
        config = AppConfig()
        assert config.language == "es"

    def test_env_output_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUDIOCORE_OUTPUT_FORMAT should load as OutputFormat enum."""
        monkeypatch.setenv("AUDIOCORE_OUTPUT_FORMAT", "json")
        config = AppConfig()
        assert config.output_format == OutputFormat.JSON

    def test_env_backend_preference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUDIOCORE_BACKEND_PREFERENCE should load as SelectionPolicy enum."""
        monkeypatch.setenv("AUDIOCORE_BACKEND_PREFERENCE", "prefer_local")
        config = AppConfig()
        assert config.backend_preference == SelectionPolicy.PREFER_LOCAL

    def test_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUDIOCORE_OPENAI_API_KEY should load into SecretStr."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-test-key-123")
        config = AppConfig()
        # SecretStr.get_secret_value() returns the actual value
        assert config.openai_api_key is not None
        assert config.openai_api_key.get_secret_value() == "sk-test-key-123"


class TestEnumTypeCoercion:
    """Test enum type coercion from string environment variables."""

    def test_backend_case_insensitive_uppercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Backend enum should accept uppercase string."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "OPENAI")
        config = AppConfig()
        assert config.backend == BackendType.OPENAI

    def test_backend_case_insensitive_lowercase(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Backend enum should accept lowercase string."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "faster_whisper")
        config = AppConfig()
        assert config.backend == BackendType.FASTER_WHISPER

    def test_backend_case_insensitive_mixed_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Backend enum should accept mixed case string."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "Auto")
        config = AppConfig()
        assert config.backend == BackendType.AUTO

    def test_model_size_coercion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Model size should be coerced from string."""
        monkeypatch.setenv("AUDIOCORE_MODEL", "small")
        config = AppConfig()
        assert config.model_size == ModelSize.SMALL

    def test_output_format_coercion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Output format should be coerced from string."""
        monkeypatch.setenv("AUDIOCORE_OUTPUT_FORMAT", "SRT")
        config = AppConfig()
        assert config.output_format == OutputFormat.SRT

    def test_selection_policy_coercion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Selection policy should be coerced from string."""
        monkeypatch.setenv("AUDIOCORE_BACKEND_PREFERENCE", "PREFER_CLOUD")
        config = AppConfig()
        assert config.backend_preference == SelectionPolicy.PREFER_CLOUD


class TestSecretStrMasking:
    """Test SecretStr masking in string representation."""

    def test_str_does_not_reveal_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """str() should not reveal API key."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-secret-12345")
        config = AppConfig()
        assert "sk-secret-12345" not in str(config)

    def test_repr_does_not_reveal_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """repr() should not reveal API key."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-secret-12345")
        config = AppConfig()
        assert "sk-secret-12345" not in repr(config)

    def test_model_dump_masks_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """model_dump() should mask API key by default."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-secret-12345")
        config = AppConfig()
        dumped = config.model_dump()
        assert "sk-secret-12345" not in str(dumped["openai_api_key"])

    def test_model_dump_reveals_with_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """model_dump() should reveal API key with hide_secrets=False."""
        monkeypatch.setenv("AUDIOCORE_OPENAI_API_KEY", "sk-secret-12345")
        config = AppConfig()
        dumped = config.model_dump(context={"hide_secrets": False})
        assert dumped["openai_api_key"].get_secret_value() == "sk-secret-12345"

    def test_top_level_openai_api_key_overrides_nested_key(self) -> None:
        """Top-level OpenAI API key should take priority over nested openai.api_key."""
        config = AppConfig(
            openai_api_key=SecretStr("sk-top-level"),
            openai=OpenAIConfig(api_key=SecretStr("sk-nested")),
        )

        assert config.openai.api_key is not None
        assert config.openai.api_key.get_secret_value() == "sk-top-level"

    def test_blank_top_level_openai_api_key_does_not_override_nested_key(self) -> None:
        """Blank top-level key should not replace a valid nested OpenAI key."""
        config = AppConfig(
            openai_api_key=SecretStr("   "),
            openai=OpenAIConfig(api_key=SecretStr("sk-nested")),
        )

        assert config.openai.api_key is not None
        assert config.openai.api_key.get_secret_value() == "sk-nested"


class TestInvalidEnumValues:
    """Test ValidationError for invalid enum values."""

    def test_invalid_backend_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid backend value should raise ValidationError."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "invalid_backend")
        with pytest.raises(ValidationError) as exc_info:
            AppConfig()
        assert "backend" in str(exc_info.value).lower()

    def test_invalid_model_raises_validation_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid model size should raise ValidationError."""
        monkeypatch.setenv("AUDIOCORE_MODEL", "huge")
        with pytest.raises(ValidationError) as exc_info:
            AppConfig()
        assert "model" in str(exc_info.value).lower()

    def test_invalid_output_format_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid output format should raise ValidationError."""
        monkeypatch.setenv("AUDIOCORE_OUTPUT_FORMAT", "invalid_format")
        with pytest.raises(ValidationError) as exc_info:
            AppConfig()
        assert "output_format" in str(exc_info.value).lower()

    def test_invalid_selection_policy_raises_validation_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid selection policy should raise ValidationError."""
        monkeypatch.setenv("AUDIOCORE_BACKEND_PREFERENCE", "prefer_invalid")
        with pytest.raises(ValidationError) as exc_info:
            AppConfig()
        assert "backend_preference" in str(exc_info.value).lower()

    @pytest.mark.parametrize("field_name", ["ffmpeg_path", "ffprobe_path"])
    def test_empty_media_tool_path_raises_validation_error(self, field_name: str) -> None:
        """Media tool paths must not be empty or whitespace-only."""
        with pytest.raises(ValidationError) as exc_info:
            AppConfig(**{field_name: "   "})

        assert field_name in str(exc_info.value)


class TestCaseInsensitiveEnvVars:
    """Test case_sensitive=False behavior."""

    # Note: pydantic-settings handles case_insensitivity for env var names,
    # but the field names themselves remain case-sensitive in the model

    def test_lowercase_backend_value_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Lowercase backend value should be accepted (parsed by enum)."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "openai")
        config = AppConfig()
        assert config.backend == BackendType.OPENAI

    def test_uppercase_backend_value_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Uppercase backend value should be accepted (parsed by enum)."""
        monkeypatch.setenv("AUDIOCORE_BACKEND", "FASTER_WHISPER")
        config = AppConfig()
        assert config.backend == BackendType.FASTER_WHISPER


class TestModelSizeProperty:
    """Test model_size property for backwards compatibility."""

    def test_model_size_property_returns_model_value(self) -> None:
        """model_size property should return the default model field value (BASE)."""
        config = AppConfig()
        assert config.model_size == ModelSize.BASE

    def test_model_size_matches_env_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """model_size should match AUDIOCORE_MODEL env var."""
        monkeypatch.setenv("AUDIOCORE_MODEL", "medium")
        config = AppConfig()
        assert config.model_size == ModelSize.MEDIUM


class TestVADConfigStrictVad:
    """Regression: VADConfig must have strict_vad field."""

    def test_vad_config_has_strict_vad_field(self) -> None:
        """VADConfig should have a strict_vad field defaulting to False."""
        from audiocore.vad.config import VADConfig

        vad = VADConfig()
        assert hasattr(vad, "strict_vad")
        assert vad.strict_vad is False

    def test_vad_config_strict_vad_can_be_set_true(self) -> None:
        """VADConfig.strict_vad should accept True value."""
        from audiocore.vad.config import VADConfig

        vad = VADConfig(strict_vad=True)
        assert vad.strict_vad is True

    def test_app_config_vad_has_strict_vad(self) -> None:
        """AppConfig.vad should include strict_vad field."""
        config = AppConfig()
        assert hasattr(config.vad, "strict_vad")
        assert config.vad.strict_vad is False
