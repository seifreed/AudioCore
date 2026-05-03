"""Configuration merger for priority chain merging.

Provides merge_configs function that combines configuration sources with
correct priority: CLI arguments (highest) > environment variables > TOML config > defaults (lowest).

Also provides load_config convenience function that loads from all sources
and returns a merged AppConfig instance.
"""

from pathlib import Path
from typing import Any

from pydantic import SecretStr
from pydantic_core import PydanticUndefined

from audiocore.config.settings import AppConfig
from audiocore.config.toml_loader import load_toml_config

_SENSITIVE_KEY_PATTERNS = ("api_key", "secret", "password", "token")


def _get_defaults() -> dict[str, Any]:
    """Extract default values from AppConfig field definitions.

    Returns:
        Dictionary mapping field names to their default values.
        SecretStr defaults are converted to empty strings for merging.
        None defaults are included in the dictionary.

    Example:
        >>> defaults = _get_defaults()
        >>> defaults["backend"]
        <BackendType.AUTO: 'auto'>
        >>> defaults["model"]
        <ModelSize.BASE: 'base'>
    """
    defaults: dict[str, Any] = {}

    for field_name, field_info in AppConfig.model_fields.items():
        if field_info.default_factory is not None:
            # Has a default_factory, call it to get default
            defaults[field_name] = field_info.default_factory()  # type: ignore[misc]
        elif field_info.default is not None and field_info.default is not PydanticUndefined:
            defaults[field_name] = field_info.default
        else:
            # Field is optional (default=None for optional fields)
            # Include it with None value
            defaults[field_name] = None

    return defaults


def mask_secrets(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Replace SecretStr values and sensitive keys with redacted placeholder.

    Used before logging or displaying configuration to prevent
    accidental exposure of sensitive values like API keys.

    Args:
        config_dict: Configuration dictionary potentially containing SecretStr values.

    Returns:
        New dictionary with SecretStr values replaced by "***REDACTED***".

    Example:
        >>> config = {"openai_api_key": SecretStr("sk-secret"), "backend": "auto"}
        >>> masked = mask_secrets(config)
        >>> masked["openai_api_key"]
        '***REDACTED***'
        >>> masked["backend"]
        'auto'
    """
    result: dict[str, Any] = {}

    for key, value in config_dict.items():
        if isinstance(value, SecretStr):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = mask_secrets(value)
        elif hasattr(value, "model_dump") and hasattr(value, "model_fields"):
            result[key] = mask_secrets(value.model_dump())
        elif isinstance(value, str) and any(p in key.lower() for p in _SENSITIVE_KEY_PATTERNS):
            result[key] = "***REDACTED***"
        else:
            result[key] = value

    return result


def merge_configs(
    defaults: dict[str, Any],
    toml: dict[str, Any],
    env: dict[str, Any],
    cli: dict[str, Any],
) -> dict[str, Any]:
    """Merge configuration sources with correct priority.

    Priority (highest to lowest):
    1. CLI arguments (cli_overrides)
    2. Environment variables (from BaseSettings)
    3. TOML config file
    4. Hardcoded defaults

    None values are skipped during merge. Track source of each value
    for debug logging.

    Args:
        defaults: Default values extracted from AppConfig fields.
        toml: Configuration loaded from TOML file.
        env: Configuration from environment variables (via AppState).
        cli: CLI argument overrides.

    Returns:
        Merged dictionary ready for AppConfig(**result).

    Example:
        >>> defaults = {"backend": "auto", "model_size": "base"}
        >>> toml = {"backend": "faster_whisper"}
        >>> env = {"backend": "openai"}
        >>> cli = {"model_size": "large"}
        >>> result = merge_configs(defaults, toml, env, cli)
        >>> result["backend"]
        'openai'  # env overrides toml
        >>> result["model_size"]
        'large'  # cli overrides defaults
    """
    # Field name mapping: TOML/config uses model_size, AppConfig uses model
    # TOML loader already outputs model_size, we need to map to model field
    field_aliases = {"model_size": "model"}

    def _normalize_keys(d: dict[str, Any]) -> dict[str, Any]:
        """Map aliased field names to actual AppConfig field names."""
        result: dict[str, Any] = {}
        for key, value in d.items():
            actual_key = field_aliases.get(key, key)
            result[actual_key] = value
        return result

    # Normalize keys for all sources
    norm_defaults = _normalize_keys(defaults)
    norm_toml = _normalize_keys(toml)
    norm_env = _normalize_keys(env)
    norm_cli = _normalize_keys(cli)

    merged: dict[str, Any] = {}

    # Apply in reverse priority order (defaults first, then each higher priority)
    # Lower priority values are overwritten by higher priority values

    # 1. Start with defaults (lowest priority)
    # Note: defaults can have None values (for optional fields), include them
    merged.update(norm_defaults)

    # 2. TOML config overrides defaults (skip None values)
    for key, value in norm_toml.items():
        if value is not None:
            merged[key] = value

    # 3. Environment variables override TOML (skip None values)
    # For sub-model dicts, merge at the sub-field level so that
    # TOML sub-fields not overridden by env are preserved.
    for key, value in norm_env.items():
        if value is not None:
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                # Merge sub-fields: env overrides only the fields it set
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value

    # 4. CLI arguments override everything (skip None values)
    for key, value in norm_cli.items():
        if value is not None:
            merged[key] = value

    return merged


def load_config(
    config_path: Path | str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """Load configuration from all sources with correct priority.

    Convenience function that:
    1. Gets defaults from AppConfig fields
    2. Loads TOML config (returns {} if missing)
    3. Creates temporary AppConfig to get env-derived values
    4. Applies CLI overrides if provided
    5. Merges all sources with correct priority
    6. Returns AppConfig instance with merged values

    Args:
        config_path: Optional path to TOML config file.
            If None, uses DEFAULT_CONFIG_PATH (~/.config/audiocore/config.toml).
            Accepts Path or string path.
        cli_overrides: Optional dictionary of CLI argument overrides.
            These have highest priority.

    Returns:
        AppConfig instance with merged values from all sources.

    Example:
        >>> from pathlib import Path
        >>> config = load_config()
        >>> config.backend
        <BackendType.AUTO: 'auto'>

        >>> # With TOML override
        >>> config = load_config(config_path=Path("custom.toml"))
        >>> config.model_size
        <ModelSize.LARGE: 'large'>

        >>> # With CLI override
        >>> config = load_config(cli_overrides={"backend": "openai"})
        >>> config.backend
        <BackendType.OPENAI: 'openai'>
    """
    import logging

    logger = logging.getLogger(__name__)

    # 1. Get defaults from AppConfig fields
    defaults = _get_defaults()

    # 2. Convert string path to Path if needed
    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path) if isinstance(config_path, str) else config_path

    # 3. Load TOML config (returns {} if missing)
    toml_config = load_toml_config(resolved_path)

    # 4. Get env values from AppConfig (without CLI overrides)
    # Create a temporary instance to get env-derived values
    # AppConfig uses pydantic-settings which reads from environment
    env_config_instance = AppConfig()

    # Extract field values that would come from env (non-default values)
    # Compare against defaults to identify env overrides.
    # For sub-models (like `openai`, `vad`), compare each sub-field individually
    # to avoid false positives from object identity comparison.
    env_values: dict[str, Any] = {}
    for field_name in AppConfig.model_fields:
        default_value = defaults.get(field_name)
        current_value = getattr(env_config_instance, field_name)

        # Determine if this value differs from default
        # For SecretStr, compare the secret values
        if isinstance(current_value, SecretStr):
            default_secret = (
                default_value if isinstance(default_value, SecretStr) else SecretStr("")
            )
            current_secret = SecretStr(current_value.get_secret_value())
            if current_secret.get_secret_value() != default_secret.get_secret_value():
                env_values[field_name] = current_value
        elif hasattr(current_value, "model_fields") and hasattr(default_value, "model_fields"):
            # Both are Pydantic models — compare sub-fields individually
            sub_env: dict[str, Any] = {}
            for sub_field_name in current_value.model_fields:
                current_sub = getattr(current_value, sub_field_name)
                default_sub = getattr(default_value, sub_field_name, None)
                # For SecretStr sub-fields, compare secret values
                if isinstance(current_sub, SecretStr):
                    default_secret_sub = (
                        default_sub if isinstance(default_sub, SecretStr) else SecretStr("")
                    )
                    if current_sub.get_secret_value() != default_secret_sub.get_secret_value():
                        sub_env[sub_field_name] = current_sub
                elif current_sub != default_sub:
                    sub_env[sub_field_name] = current_sub
            if sub_env:
                env_values[field_name] = sub_env
        elif current_value != default_value:
            env_values[field_name] = current_value

    # 5. CLI overrides (highest priority)
    # Also map model_size to model for CLI
    field_aliases = {"model_size": "model"}
    cli_config: dict[str, Any] = {}
    if cli_overrides:
        for key, value in cli_overrides.items():
            actual_key = field_aliases.get(key, key)
            cli_config[actual_key] = value

    # 6. Merge all sources
    merged = merge_configs(defaults, toml_config, env_values, cli_config)

    # 7. Log configuration sources at DEBUG level
    # Never log API keys in plain text
    logger.debug("Configuration loaded:")
    logger.debug(
        "  Defaults: %s",
        {k: v for k, v in mask_secrets(defaults).items() if v is not None},
    )
    logger.debug(
        "  TOML: %s",
        {k: v for k, v in mask_secrets(toml_config).items() if v is not None},
    )
    logger.debug(
        "  Env: %s",
        {k: v for k, v in mask_secrets(env_values).items() if v is not None},
    )
    logger.debug(
        "  CLI: %s",
        {k: v for k, v in mask_secrets(cli_config).items() if v is not None},
    )

    # Track source of each value for debugging
    source_tracking: dict[str, str] = {}
    for field_name in AppConfig.model_fields:
        if field_name in cli_config and cli_config[field_name] is not None:
            source_tracking[field_name] = "CLI"
        elif field_name in env_values and env_values[field_name] is not None:
            source_tracking[field_name] = "ENV"
        elif field_name in toml_config and toml_config[field_name] is not None:
            source_tracking[field_name] = "TOML"
        else:
            source_tracking[field_name] = "DEFAULT"

    logger.debug("  Sources: %s", source_tracking)

    # 8. Create AppConfig from merged values
    # Use model_validate to construct from dict, respecting validators
    return AppConfig.model_validate(merged)
