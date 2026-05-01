"""TOML configuration file loader.

Provides functions for loading configuration from TOML files with
path expansion, error handling, and flattened key extraction.
"""

import tomllib
from pathlib import Path
from typing import Any

from audiocore.errors import InvalidConfigError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "audiocore" / "config.toml"
"""Default configuration file path: ~/.config/audiocore/config.toml"""

# Fields that should be converted to Path objects
_PATH_FIELDS = {"model_cache_path", "temp_path"}

# Mapping from TOML flat keys to AppConfig field names.
# Also maps nested TOML keys (e.g. "openai.api_key") to their nested form.
_FIELD_MAPPING = {
    "backend.backend": "backend",
    "backend.model_size": "model",
    "backend.backend_preference": "backend_preference",
    "output.output_format": "output_format",
    "paths.model_cache_path": "model_cache_path",
    "paths.temp_path": "temp_path",
    "language.language": "language",
    # OpenAI nested config
    "openai.api_key": "openai.api_key",
    "openai.organization": "openai.organization",
    "openai.base_url": "openai.base_url",
    "openai.timeout": "openai.timeout",
    "openai.max_retries": "openai.max_retries",
    # VAD nested config
    "vad.speech_threshold": "vad.speech_threshold",
    "vad.silence_threshold": "vad.silence_threshold",
    "vad.min_segment_duration": "vad.min_segment_duration",
    "vad.min_silence_duration_ms": "vad.min_silence_duration_ms",
    "vad.window_size_samples": "vad.window_size_samples",
    "vad.strict_vad": "vad.strict_vad",
}


def _flatten_toml_section(section: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested TOML section into dot-notation keys.

    TOML sections are nested like:
        [backend]
        backend = "auto"
        model_size = "base"

    Or with nested sections:
        [openai]
        api_key = "sk-..."
        timeout = 60

        [vad]
        speech_threshold = 0.5

    This function flattens to match AppConfig field names, preserving
    nested structure for sub-models (openai, vad) using dot notation
    that can be unflattened later.

    Path fields (model_cache_path, temp_path) are converted to Path objects
    with ~ expansion applied.

    Args:
        section: Nested dictionary from TOML parsing
        prefix: Key prefix for recursion (internal use)

    Returns:
        Flattened dictionary with keys matching AppConfig field names
    """
    result: dict[str, Any] = {}

    for key, value in section.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            # Recurse into nested sections
            result.update(_flatten_toml_section(value, full_key))
        else:
            # Map to AppConfig field name using the mapping table
            field_name = _FIELD_MAPPING.get(full_key, key)

            # Convert path fields to Path objects with ~ expansion
            if field_name in _PATH_FIELDS and isinstance(value, str):
                result[field_name] = Path(value).expanduser()
            else:
                result[field_name] = value

    return result


def _unflatten_nested(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert dot-notation keys back into nested dicts for Pydantic sub-models.

    Keys like "openai.api_key" become {"openai": {"api_key": value}}.
    Non-dotted keys are left as-is.

    Args:
        flat: Flattened dictionary with possible dot-notation keys.

    Returns:
        Dictionary with nested sub-dicts for sub-models.
    """
    result: dict[str, Any] = {}
    nested: dict[str, dict[str, Any]] = {}

    for key, value in flat.items():
        if "." in key:
            top_key, _, sub_key = key.partition(".")
            if top_key not in nested:
                nested[top_key] = {}
            nested[top_key][sub_key] = value
        else:
            result[key] = value

    # Merge nested dicts into result
    for top_key, sub_dict in nested.items():
        result[top_key] = sub_dict

    return result


def load_toml_config(path: Path | None = None) -> dict[str, Any]:
    """Load configuration from a TOML file.

    Loads configuration from the specified path (or default path) and
    flattens nested sections into a dictionary matching AppConfig field names.

    Missing files return an empty dictionary (not an error).
    Invalid TOML syntax or permission errors raise InvalidConfigError.

    Args:
        path: Optional path to the TOML file. If None, uses DEFAULT_CONFIG_PATH.

    Returns:
        Dictionary with configuration keys matching AppConfig fields,
        with nested sub-models as nested dicts.

    Raises:
        InvalidConfigError: If the file cannot be read or contains invalid TOML.

    Example:
        >>> config = load_toml_config()  # Uses default path
        >>> config["backend"]
        'openai'
        >>> config = load_toml_config(Path("~/my_config.toml"))
        >>> config["model"]
        'medium'
    """
    config_path = (path or DEFAULT_CONFIG_PATH).expanduser()

    # Handle missing file
    if not config_path.exists():
        return {}

    # Handle permission error
    if not config_path.is_file():
        raise InvalidConfigError(
            f"Configuration path is not a file: {config_path}",
            context={"path": str(config_path)},
        )

    # Read and parse TOML
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except PermissionError as e:
        raise InvalidConfigError(
            f"Permission denied reading configuration file: {config_path}",
            context={"path": str(config_path), "error": str(e)},
            cause=e,
        ) from e
    except tomllib.TOMLDecodeError as e:
        raise InvalidConfigError(
            f"Invalid TOML syntax in configuration file: {config_path}",
            context={
                "path": str(config_path),
                "line": getattr(e, "lineno", None),
                "column": getattr(e, "colno", None),
                "error": str(e),
            },
            cause=e,
        ) from e

    # Flatten nested sections to match AppConfig field names
    flat = _flatten_toml_section(data)

    # Unflatten nested sub-model keys (openai.api_key -> {openai: {api_key: ...}})
    return _unflatten_nested(flat)