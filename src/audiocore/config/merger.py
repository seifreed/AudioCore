"""Configuration merger for priority chain merging.

Provides merge_configs function that combines configuration sources with
correct priority: CLI arguments (highest) > environment variables > TOML config > defaults (lowest).

Also provides load_config convenience function that loads from all sources
and returns a merged AppConfig instance.
"""

from pathlib import Path
from typing import Any

from pydantic import SecretStr

from audiocore.config.settings import AppConfig
from audiocore.config.toml_loader import DEFAULT_CONFIG_PATH, load_toml_config


def _get_defaults() -> dict[str, Any]:
    """Extract default values from AppConfig field definitions.

    Returns:
        Dictionary mapping field names to their default values.
        SecretStr defaults are converted to empty strings for merging.

    Example:
        >>> defaults = _get_defaults()
        >>> defaults["backend"]
        <BackendType.AUTO: 'auto'>
        >>> defaults["model_size"]
        <ModelSize.BASE: 'base'>
    """
    defaults: dict[str, Any] = {}

    for field_name, field_info in AppConfig.model_fields.items():
        if field_info.default_factory is not None:
            # Has a default_factory, call it to get default
            defaults[field_name] = field_info.default_factory()
        elif field_info.default is not None:
            # Has a direct default value
            defaults[field_name] = field_info.default
        # If both are None, the field is required (shouldn't happen for AppConfig)

    return defaults


def mask_secrets(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Replace SecretStr values with redacted placeholder.

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
            # Recursively mask nested dicts
            result[key] = mask_secrets(value)
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
    merged: dict[str, Any] = {}

    # Apply in reverse priority order (defaults first, then each higher priority)
    # Lower priority values are overwritten by higher priority values

    # 1. Start with defaults (lowest priority)
    for key, value in defaults.items():
        if value is not None:
            merged[key] = value

    # 2. TOML config overrides defaults
    for key, value in toml.items():
        if value is not None:
            merged[key] = value

    # 3. Environment variables override TOML
    for key, value in env.items():
        if value is not None:
            merged[key] = value

    # 4. CLI arguments override everything (highest priority)
    for key, value in cli.items():
        if value is not None:
            merged[key] = value

    return merged


def load_config(
    config_path: Path | None = None,
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

    # 2. Load TOML config (returns {} if missing)
    toml_config = load_toml_config(config_path)

    # 3. Get env values from AppConfig (without CLI overrides)
    # Create a temporary instance to get env-derived values
    # AppConfig uses pydantic-settings which reads from environment
    env_config_instance = AppConfig()

    # Extract field values that would come from env (non-None values)
    # We use model_dump to get the actual values, then mask secrets for logging
    env_values: dict[str, Any] = {}
    for field_name in AppConfig.model_fields:
        value = getattr(env_config_instance, field_name)
        # Only include non-default values (those from env)
        if value is not None and value != defaults.get(field_name):
            env_values[field_name] = value

    # 4. CLI overrides (highest priority)
    cli_config = cli_overrides or {}

    # 5. Merge all sources
    merged = merge_configs(defaults, toml_config, env_values, cli_config)

    # 6. Log configuration sources at DEBUG level
    # Never log API keys in plain text
    merged_for_log = mask_secrets(merged)

    logger.debug("Configuration loaded:")
    logger.debug(
        "  Defaults: %s", {k: v for k, v in mask_secrets(defaults).items() if v is not None}
    )
    logger.debug(
        "  TOML: %s", {k: v for k, v in mask_secrets(toml_config).items() if v is not None}
    )
    logger.debug(
        "  Env: %s",
        {k: "***REDACTED***" if k == "openai_api_key" else v for k, v in env_values.items()},
    )
    logger.debug("  CLI: %s", {k: v for k, v in mask_secrets(cli_config).items() if v is not None})

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

    # 7. Create AppConfig from merged values
    # Use model_validate to construct from dict, respecting validators
    return AppConfig.model_validate(merged)
