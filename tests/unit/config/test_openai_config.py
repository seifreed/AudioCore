"""Unit tests for OpenAIConfig configuration model.

Tests default values, SecretStr handling, validation, and integration
with OpenAIBackend and AppConfig.
"""

import pytest
from pydantic import SecretStr

from audiocore.backends.openai_backend import OpenAIBackend
from audiocore.config.openai_config import OpenAIConfig
from audiocore.config.settings import AppConfig


class TestOpenAIConfigDefaults:
    """Test default values for all OpenAIConfig fields."""

    def test_default_api_key_is_none(self) -> None:
        """Default api_key should be None."""
        config = OpenAIConfig()
        assert config.api_key is None

    def test_default_organization_is_none(self) -> None:
        """Default organization should be None."""
        config = OpenAIConfig()
        assert config.organization is None

    def test_default_base_url_is_none(self) -> None:
        """Default base_url should be None."""
        config = OpenAIConfig()
        assert config.base_url is None

    def test_default_timeout_is_300(self) -> None:
        """Default timeout should be 300 seconds."""
        config = OpenAIConfig()
        assert config.timeout == 300

    def test_default_max_retries_is_2(self) -> None:
        """Default max_retries should be 2."""
        config = OpenAIConfig()
        assert config.max_retries == 2


class TestOpenAIConfigSecretStr:
    """Test SecretStr handling for API key."""

    def test_api_key_stored_as_secret_str(self) -> None:
        """api_key should be stored as SecretStr."""
        config = OpenAIConfig(api_key="sk-test-key-123")
        assert isinstance(config.api_key, SecretStr)

    def test_api_key_get_secret_value_returns_string(self) -> None:
        """get_secret_value() should return the actual API key string."""
        config = OpenAIConfig(api_key="sk-test-key-123")
        assert config.api_key.get_secret_value() == "sk-test-key-123"

    def test_str_does_not_reveal_api_key(self) -> None:
        """str() should mask the API key."""
        config = OpenAIConfig(api_key="sk-secret-12345")
        assert "sk-secret-12345" not in str(config)

    def test_repr_does_not_reveal_api_key(self) -> None:
        """repr() should mask the API key."""
        config = OpenAIConfig(api_key="sk-secret-12345")
        assert "sk-secret-12345" not in repr(config)

    def test_model_dump_masks_api_key(self) -> None:
        """model_dump() should mask API key by default."""
        config = OpenAIConfig(api_key="sk-secret-12345")
        dumped = config.model_dump()
        # SecretStr serializes as '**********' by default
        assert "sk-secret-12345" not in str(dumped["api_key"])


class TestOpenAIConfigValidation:
    """Test field validation."""

    def test_timeout_min_value(self) -> None:
        """timeout should accept minimum value of 1."""
        config = OpenAIConfig(timeout=1)
        assert config.timeout == 1

    def test_timeout_max_value(self) -> None:
        """timeout should accept maximum value of 3600."""
        config = OpenAIConfig(timeout=3600)
        assert config.timeout == 3600

    def test_timeout_invalid_below_min(self) -> None:
        """timeout below minimum should raise ValidationError."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            OpenAIConfig(timeout=0)

    def test_timeout_invalid_above_max(self) -> None:
        """timeout above maximum should raise ValidationError."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            OpenAIConfig(timeout=3601)

    def test_max_retries_min_value(self) -> None:
        """max_retries should accept minimum value of 0."""
        config = OpenAIConfig(max_retries=0)
        assert config.max_retries == 0

    def test_max_retries_max_value(self) -> None:
        """max_retries should accept maximum value of 10."""
        config = OpenAIConfig(max_retries=10)
        assert config.max_retries == 10

    def test_max_retries_invalid_below_min(self) -> None:
        """max_retries below minimum should raise ValidationError."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            OpenAIConfig(max_retries=-1)

    def test_max_retries_invalid_above_max(self) -> None:
        """max_retries above maximum should raise ValidationError."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            OpenAIConfig(max_retries=11)

    def test_extra_fields_forbidden(self) -> None:
        """Additional fields should be rejected."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            OpenAIConfig(unknown_field="value")  # type: ignore[call-arg]


class TestOpenAIConfigOptionalFields:
    """Test optional field handling."""

    def test_organization_accepts_string(self) -> None:
        """organization should accept a string value."""
        config = OpenAIConfig(organization="org-123")
        assert config.organization == "org-123"

    def test_base_url_accepts_string(self) -> None:
        """base_url should accept a string URL."""
        config = OpenAIConfig(base_url="https://api.custom-openai.com")
        assert config.base_url == "https://api.custom-openai.com"

    def test_api_key_accepts_none(self) -> None:
        """api_key should accept None."""
        config = OpenAIConfig(api_key=None)
        assert config.api_key is None


class TestAppConfigOpenAIIntegration:
    """Test OpenAIConfig integration into AppConfig."""

    def test_appconfig_contains_openai_field(self) -> None:
        """AppConfig should contain openai field with OpenAIConfig."""
        config = AppConfig()
        assert hasattr(config, "openai")
        assert isinstance(config.openai, OpenAIConfig)

    def test_appconfig_openai_uses_defaults(self) -> None:
        """AppConfig.openai should use default OpenAIConfig values."""
        config = AppConfig()
        assert config.openai.api_key is None
        assert config.openai.timeout == 300
        assert config.openai.max_retries == 2

    def test_appconfig_openai_with_custom_config(self) -> None:
        """AppConfig should accept custom OpenAIConfig."""
        openai_config = OpenAIConfig(
            api_key="sk-custom-key",
            timeout=600,
            max_retries=5,
        )
        config = AppConfig(openai=openai_config)
        assert config.openai.api_key.get_secret_value() == "sk-custom-key"
        assert config.openai.timeout == 600
        assert config.openai.max_retries == 5


class TestOpenAIBackendConfigIntegration:
    """Test OpenAIBackend integration with OpenAIConfig."""

    def test_backend_accepts_config_parameter(self) -> None:
        """OpenAIBackend should accept config parameter."""
        config = OpenAIConfig(api_key="sk-test-123")
        backend = OpenAIBackend(config=config)
        assert backend._config is not None
        assert backend._api_key == "sk-test-123"

    def test_backend_prioritizes_config_over_api_key(self) -> None:
        """Config.api_key should take precedence over api_key parameter."""
        config = OpenAIConfig(api_key="sk-config-key")
        backend = OpenAIBackend(config=config, api_key="sk-param-key")
        assert backend._api_key == "sk-config-key"

    def test_backend_uses_api_key_when_no_config(self) -> None:
        """OpenAIBackend should use api_key parameter without config."""
        backend = OpenAIBackend(api_key="sk-param-key")
        assert backend._api_key == "sk-param-key"
        assert backend._config is None

    def test_backend_uses_environment_when_no_config_or_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenAIBackend should use environment variable as fallback."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        backend = OpenAIBackend()
        assert backend._api_key is None  # Not set, will use env at client init
        assert backend.is_available() is True

    def test_backend_is_available_with_config(self) -> None:
        """is_available should return True with valid config."""
        config = OpenAIConfig(api_key="sk-valid-key")
        backend = OpenAIBackend(config=config)
        assert backend.is_available() is True

    def test_backend_is_available_with_invalid_key_format(self) -> None:
        """is_available should return False with invalid key format."""
        config = OpenAIConfig(api_key="invalid-key")
        backend = OpenAIBackend(config=config)
        assert backend.is_available() is False

    def test_backend_preserves_config_reference(self) -> None:
        """OpenAIBackend should preserve config reference for defaults."""
        config = OpenAIConfig(
            api_key="sk-test-key",
            organization="org-123",
            base_url="https://api.custom.com",
            timeout=600,
        )
        backend = OpenAIBackend(config=config)
        assert backend._config is config


class TestConfigPriority:
    """Test configuration priority chain."""

    def test_priority_config_over_api_key(self) -> None:
        """Config should have highest priority."""
        config = OpenAIConfig(api_key="sk-config-key")
        backend = OpenAIBackend(config=config, api_key="sk-param-key")
        assert backend._api_key == "sk-config-key"

    def test_priority_api_key_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """api_key should have priority over environment variable."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        backend = OpenAIBackend(api_key="sk-param-key")
        # api_key parameter takes precedence
        assert backend._api_key == "sk-param-key"

    def test_priority_env_as_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variable should be fallback when no config or api_key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key")
        backend = OpenAIBackend()
        assert backend._api_key is None  # Not set in __init__
        assert backend.is_available() is True  # But env var makes it available
