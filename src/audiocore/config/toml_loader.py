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


def _flatten_toml_section(section: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested TOML section into dot-notation keys.

    TOML sections are nested like:
        [backend]
        backend = "auto"
        model_size = "base"

    This function flattens to match AppConfig field names:
        backend -> backend
        model_size -> model_size

    Path fields (model_cache_path, temp_path) are converted to Path objects
    with ~ expansion applied.

    Args:
        section: Nested dictionary from TOML parsing
        prefix: Key prefix for recursion (internal use)

    Returns:
        Flattened dictionary with keys matching AppConfig field names

    Example:
        >>> data = {"backend": {"backend": "openai", "model_size": "medium"}}
        >>> _flatten_toml_section(data)
        {"backend": "openai", "model_size": "medium"}
    """
    result: dict[str, Any] = {}

    # Mapping from TOML section.key to AppConfig field name
    field_mapping = {
        "backend.backend": "backend",
        "backend.model_size": "model_size",
        "backend.backend_preference": "backend_preference",
        "output.output_format": "output_format",
        "paths.model_cache_path": "model_cache_path",
        "paths.temp_path": "temp_path",
        "language.language": "language",
    }

    for key, value in section.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            # Recurse into nested sections
            result.update(_flatten_toml_section(value, full_key))
        else:
            # Map to AppConfig field name or use the key directly
            field_name = field_mapping.get(full_key, key)

            # Convert path fields to Path objects with ~ expansion
            if field_name in _PATH_FIELDS and isinstance(value, str):
                result[field_name] = Path(value).expanduser()
            else:
                result[field_name] = value

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
        Dictionary with flattened configuration keys matching AppConfig fields.

    Raises:
        InvalidConfigError: If the file cannot be read or contains invalid TOML.

    Example:
        >>> config = load_toml_config()  # Uses default path
        >>> config["backend"]
        'openai'
        >>> config = load_toml_config(Path("~/my_config.toml"))
        >>> config["model_size"]
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
    return _flatten_toml_section(data)
