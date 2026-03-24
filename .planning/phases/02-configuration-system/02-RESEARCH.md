# Phase 2: Configuration System - Research

**Phase Goal**: Flexible configuration from environment, files, and defaults with clear priority

**Requirements**: CONF-01, CONF-02, CONF-03

---

## 1. Domain Analysis

### Configuration Sources (Priority: High → Low)

| Source | Priority | Format | Example |
|--------|----------|--------|---------|
| CLI arguments | 1 (highest) | Command flags | `--backend openai` |
| Environment variables | 2 | `AUDIOCORE_*` prefix | `AUDIOCORE_OPENAI_API_KEY=sk-...` |
| TOML config file | 3 | `~/.config/audiocore/config.toml` | TOML key-value |
| Hardcoded defaults | 4 (lowest) | Model defaults | `backend = "auto"` |

### Configuration Categories

| Category | Fields | Source Support |
|----------|--------|----------------|
| Backend selection | `backend`, `backend_preference` | All sources |
| Model settings | `model_size`, `language` | All sources |
| Output settings | `output_format` | All sources |
| API credentials | `openai_api_key` | Env vars only (security) |
| Paths | `model_cache_path`, `temp_path` | TOML + defaults |

### Environment Variable Mapping (CONF-01)

| Environment Variable | Config Field | Type | Default |
|---------------------|--------------|------|---------|
| `AUDIOCORE_OPENAI_API_KEY` | `openai_api_key` | `str \| None` | `None` |
| `AUDIOCORE_BACKEND` | `backend` | `BackendType` | `"auto"` |
| `AUDIOCORE_MODEL` | `model_size` | `ModelSize` | `"base"` |
| `AUDIOCORE_LANGUAGE` | `language` | `str \| None` | `None` |
| `AUDIOCORE_OUTPUT_FORMAT` | `output_format` | `OutputFormat` | `"text"` |

### TOML Configuration Schema (CONF-02)

```toml
# ~/.config/audiocore/config.toml

[backend]
backend = "auto"                    # BackendType: openai, faster_whisper, auto
model_size = "base"                # ModelSize: tiny, base, small, medium, large
backend_preference = "auto"         # SelectionPolicy: prefer_local, prefer_cloud, auto

[output]
output_format = "text"             # OutputFormat: text, json, srt, vtt

[paths]
model_cache_path = "~/.cache/audiocore/models"
temp_path = "/tmp/audiocore"       # Temporary file directory

[language]
language = "en"                    # ISO 639-1 language code
```

---

## 2. Implementation Strategy

### Order of Implementation

1. **Configuration model** - Pydantic model with all config fields
2. **Default values** - Hardcoded defaults in model
3. **Environment loader** - Read `AUDIOCORE_*` env vars
4. **TOML loader** - Parse config file with validation
5. **Priority merger** - Merge sources with correct priority
6. **API key masking** - Redact sensitive values in logs/displays

### Dependency Graph

```
ConfigurationError/InvalidConfigError (Phase 1)
         ↓
BackendType, ModelSize, OutputFormat, SelectionPolicy (Phase 1)
         ↓
    ConfigModel (Pydantic BaseModel)
         ↓
    ├── EnvLoader (os.environ)
    ├── TomlLoader (tomllib)
    └── ConfigMerger (priority chain)
         ↓
    AppConfig (final merged config)
```

---

## 3. Technical Decisions

### Use Pydantic BaseSettings (pydantic-settings)

| Decision | Rationale |
|----------|-----------|
| Use `pydantic-settings` package | Official Pydantic v2 settings management |
| Subclass `BaseSettings` | Built-in env var support with prefix |
| Use `SettingsConfigDict` | Clean configuration |
| Custom `env_prefix = "AUDIOCORE_"` | Matches requirement |
| Disable `env_file` | Use TOML instead of .env |

### TOML Parsing (Python 3.11+)

| Decision | Rationale |
|----------|-----------|
| Use `tomllib` (stdlib) | No external dependency |
| Read-only parsing | No TOML generation needed |
| `Path.expanduser()` | Support `~` in paths |
| Validate on load | Raise `InvalidConfigError` early |

### Priority Chain Implementation (CONF-03)

| Decision | Rationale |
|----------|-----------|
| Explicit merge order | Clear precedence documentation |
| `model_construct()` for defaults | Skip validation for defaults |
| `model_copy(update=...)` for overlay | Immutable config objects |
| Debug-level logging | Track which source provided each value |

### API Key Security

| Decision | Rationale |
|----------|-----------|
| Store in `SecretStr` | Pydantic built-in secret handling |
| Custom `__repr__` | Mask in logs and displays |
| Never serialize to JSON | Prevent accidental exposure |
| Strip from debug output | Debug logs safe |

---

## 4. Standard Patterns

### Pydantic BaseSettings Pattern

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AUDIOCORE_",
        env_file=None,  # Disable .env, use TOML
        case_sensitive=False,
        extra="forbid",
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key for authentication",
    )
    backend: BackendType = Field(
        default=BackendType.AUTO,
        description="Backend selection (openai, faster_whisper, auto)",
    )
    model_size: ModelSize = Field(
        default=ModelSize.BASE,
        description="Whisper model size",
    )
    language: str | None = Field(
        default=None,
        description="ISO 639-1 language code",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT,
        description="Output format",
    )
    backend_preference: SelectionPolicy = Field(
        default=SelectionPolicy.AUTO,
        description="Backend selection policy",
    )
```

### TOML Loading Pattern

```python
import tomllib
from pathlib import Path
from audiocore.errors import InvalidConfigError


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "audiocore" / "config.toml"


def load_toml_config(path: Path | None = None) -> dict[str, object]:
    config_path = path or DEFAULT_CONFIG_PATH
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise InvalidConfigError(
            f"Invalid TOML in config file: {e}",
            context={"file_path": str(config_path)},
            cause=e,
        ) from e
```

### Priority Merge Pattern

```python
from typing import Any


def merge_configs(
    defaults: dict[str, Any],
    toml: dict[str, Any],
    env: dict[str, Any],
    cli: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge configs with priority: CLI > env > TOML > defaults.
    
    Higher priority values override lower priority ones.
    Returns flattened dict ready for Pydantic model.
    """
    merged = {}
    
    # Track sources for debug logging
    sources: dict[str, str] = {}
    
    def apply(source_dict: dict[str, Any], source_name: str) -> None:
        for key, value in source_dict.items():
            if value is not None:
                merged[key] = value
                sources[key] = source_name
    
    # Apply in reverse priority order
    apply(defaults, "defaults")
    apply(toml, "toml")
    apply(env, "environment")
    apply(cli, "cli")
    
    # Log sources at debug level
    logger.debug(f"Config sources: {sources}")
    
    return merged
```

### Secret Masking Pattern

```python
from pydantic import SecretStr


def mask_secrets(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Replace SecretStr values with masked strings."""
    result = {}
    for key, value in config_dict.items():
        if isinstance(value, SecretStr):
            result[key] = "***REDACTED***"
        else:
            result[key] = value
    return result
```

---

## 5. Common Pitfalls

### Pydantic v2 Settings Migration

| Pitfall | Solution |
|---------|----------|
| Missing `pydantic-settings` | Add as separate dependency |
| `class Config` inner class | Use `model_config = SettingsConfigDict(...)` |
| `@validator` for env parsing | Use `@field_validator` with `mode="before"` |
| Case-sensitive env vars | Set `case_sensitive=False`, env vars auto-uppercased |
| Extra fields in TOML | Set `extra="forbid"` in model config |

### TOML Parsing Issues

| Pitfall | Solution |
|---------|----------|
| File not found | Return empty dict, not an error |
| Invalid TOML syntax | Wrap in try/except, raise `InvalidConfigError` |
| Path with `~` | Use `Path.expanduser()` |
| Permission errors | Catch `PermissionError`, raise `InvalidConfigError` |

### Priority Chain Bugs

| Pitfall | Solution |
|---------|----------|
| Wrong merge order | Apply lowest priority first, highest last |
| `None` values override | Check `value is not None` before applying |
| Missing type coercion | Let Pydantic handle conversion |
| CLI partial updates | Use `model_copy(update=...)` pattern |

### API Key Leaks

| Pitfall | Solution |
|---------|----------|
| Plain string for secrets | Use `SecretStr` type |
| Logging config dict | Always mask secrets before logging |
| `model_dump()` exposes secrets | Use `model_dump(mode="json")` or custom serializer |
| Error messages with keys | Sanitize error context |

---

## 6. Dependencies

### Already Available (Phase 1)

| Module | Usage |
|--------|-------|
| `audiocore.errors.config` | `ConfigurationError`, `InvalidConfigError` |
| `audiocore.types` | `BackendType`, `ModelSize`, `OutputFormat`, `SelectionPolicy` |

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic-settings` | ^2.0 | BaseSettings with env var support |

**Note:** `tomllib` is stdlib in Python 3.11+, no external dependency needed.

### Import Structure

```
src/audiocore/
├── config/
│   ├── __init__.py           # Re-export AppConfig, load_config
│   ├── settings.py           # AppConfig model (BaseSettings)
│   ├── env_loader.py         # Environment variable loading
│   ├── toml_loader.py        # TOML file loading
│   └── merger.py             # Priority chain merger
```

---

## 7. Testing Strategy

### Unit Test Coverage

| Module | Test Focus |
|--------|------------|
| `settings.py` | Default values, type validation, SecretStr handling |
| `env_loader.py` | Prefix matching, type coercion, missing vars |
| `toml_loader.py` | Valid TOML, invalid TOML, missing file, path expansion |
| `merger.py` | Priority order, value override, None handling |

### Test Patterns

```python
import os
from pathlib import Path
import pytest
from unittest.mock import patch

from audiocore.config import AppConfig, load_config
from audiocore.types import BackendType, ModelSize


def test_env_var_prefix():
    with patch.dict(os.environ, {"AUDIOCORE_BACKEND": "openai"}):
        config = AppConfig()
        assert config.backend == BackendType.OPENAI


def test_toml_loading(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[backend]\nbackend = "faster_whisper"')
    
    config = load_config(config_path=config_file)
    assert config.backend == BackendType.FASTER_WHISPER


def test_priority_chain(tmp_path: Path):
    # TOML says "auto", env says "openai" -> env wins
    config_file = tmp_path / "config.toml"
    config_file.write_text('[backend]\nbackend = "auto"')
    
    with patch.dict(os.environ, {"AUDIOCORE_BACKEND": "openai"}):
        config = load_config(config_path=config_file)
        assert config.backend == BackendType.OPENAI


def test_api_key_masking():
    config = AppConfig(openai_api_key="sk-secret123")
    # SecretStr automatically masks
    assert "sk-secret123" not in str(config)
    assert "sk-secret123" not in repr(config)


def test_invalid_toml(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("invalid [ toml")
    
    with pytest.raises(InvalidConfigError) as exc_info:
        load_config(config_path=config_file)
    
    assert "Invalid TOML" in str(exc_info.value)
```

### Integration Tests

| Scenario | Test |
|----------|------|
| No config, no env vars | All defaults applied |
| Missing TOML file | Defaults used, no error |
| Invalid TOML syntax | `InvalidConfigError` raised |
| Env var overrides TOML | Correct priority |
| CLI overrides env | Correct priority |
| API key in env | Properly loaded, masked in display |

### Test Organization

```
tests/
├── unit/
│   └── config/
│       ├── __init__.py
│       ├── test_settings.py
│       ├── test_env_loader.py
│       ├── test_toml_loader.py
│       └── test_merger.py
└── integration/
    └── config/
        └── test_config_priority.py
```

---

## 8. File Structure Recommendations

### Package Structure

```
src/audiocore/config/
├── __init__.py
│   # Public exports:
│   # - AppConfig
│   # - load_config()
│   # - DEFAULT_CONFIG_PATH
│
├── settings.py
│   # - AppConfig(BaseSettings)
│   # - default values
│   # - SecretStr for API key
│
├── env_loader.py
│   # - get_env_config()
│   # - env var mapping
│
├── toml_loader.py
│   # - load_toml_config()
│   # - DEFAULT_CONFIG_PATH constant
│   # - error handling
│
└── merger.py
    # - merge_configs()
    # - mask_secrets()
    # - merge flattened TOML sections
```

### Module Content Summary

| Module | Classes/Functions | Lines (est.) |
|--------|-------------------|--------------|
| `settings.py` | `AppConfig` | 60 |
| `env_loader.py` | `get_env_config()` | 30 |
| `toml_loader.py` | `load_toml_config()`, `DEFAULT_CONFIG_PATH` | 40 |
| `merger.py` | `merge_configs()`, `mask_secrets()` | 50 |
| `__init__.py` | Exports | 15 |

**Total estimated lines: ~195**

---

## 9. Key Interfaces

### AppConfig Model

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy


class AppConfig(BaseSettings):
    """Application configuration with priority chain support.
    
    Priority: CLI > environment > TOML > defaults
    
    Attributes:
        openai_api_key: OpenAI API key (from env only, never in TOML)
        backend: Backend selection
        model_size: Whisper model size
        language: ISO 639-1 language code
        output_format: Output format
        backend_preference: Automatic selection policy
        model_cache_path: Path for cached models
        temp_path: Temporary file directory
    """
    
    model_config = SettingsConfigDict(
        env_prefix="AUDIOCORE_",
        env_file=None,
        case_sensitive=False,
        extra="forbid",
    )

    openai_api_key: SecretStr | None = Field(
        default=None,
        description="OpenAI API key",
    )
    backend: BackendType = Field(
        default=BackendType.AUTO,
        description="Backend selection",
    )
    model_size: ModelSize = Field(
        default=ModelSize.BASE,
        description="Model size",
    )
    language: str | None = Field(
        default=None,
        description="Language code",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.TEXT,
        description="Output format",
    )
    backend_preference: SelectionPolicy = Field(
        default=SelectionPolicy.AUTO,
        description="Selection policy",
    )
    model_cache_path: Path | None = Field(
        default=None,
        description="Model cache path",
    )
    temp_path: Path | None = Field(
        default=None,
        description="Temp file directory",
    )
```

### load_config Function

```python
from pathlib import Path
from audiocore.config.settings import AppConfig
from audiocore.config.toml_loader import load_toml_config
from audiocore.config.merger import merge_configs


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "audiocore" / "config.toml"


def load_config(
    config_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> AppConfig:
    """Load configuration with priority chain.
    
    Args:
        config_path: Optional TOML config path (defaults to ~/.config/audiocore/config.toml)
        cli_overrides: Optional CLI arguments (highest priority)
    
    Returns:
        Merged AppConfig instance
    
    Raises:
        InvalidConfigError: If TOML file is invalid
    """
    # Load TOML (returns {} if missing)
    toml_config = load_toml_config(config_path)
    
    # Get environment config (from BaseSettings)
    env_config = _get_env_config()
    
    # CLI overrides (highest priority)
    cli_config = cli_overrides or {}
    
    # Merge with priority
    merged = merge_configs(
        defaults=_get_defaults(),
        toml=_flatten_toml(toml_config),
        env=env_config,
        cli=cli_config,
    )
    
    # Create config instance
    return AppConfig(**merged)
```

---

## 10. Pre-Implementation Checklist

- [ ] Add `pydantic-settings` to `pyproject.toml` dependencies
- [ ] Create `src/audiocore/config/` directory
- [ ] Implement `AppConfig` model with `SecretStr` for API key
- [ ] Implement TOML loader with error handling
- [ ] Implement environment variable extraction
- [ ] Implement priority merger with debug logging
- [ ] Implement API key masking utility
- [ ] Write unit tests for each component
- [ ] Write integration tests for priority chain
- [ ] Verify API key never appears in logs
- [ ] Verify `model_dump()` respects `SecretStr`

---

## 11. Open Questions for Planning

1. **Should CLI arguments be parsed in this phase or deferred to Phase 10?**
   - Recommendation: Define interface now, implement parsing in CLI phase
   - Accept `cli_overrides: dict[str, Any]` parameter for future CLI integration

2. **Should TOML config use nested sections or flat keys?**
   - TOML: `[backend]`, `[output]`, `[paths]` sections
   - Flatten during merge to match model fields
   - Recommendation: Nested sections for readability

3. **Should config file path be configurable via env var?**
   - `AUDIOCORE_CONFIG_PATH` for custom config location
   - Recommendation: Yes, useful for testing and deployment

4. **Should there be a `config show` CLI command?**
   - Displays current config with source annotations
   - Part of CLI-04, not this phase
   - Prepare data structure for future use