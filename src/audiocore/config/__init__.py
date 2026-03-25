"""Configuration module for AudioCore.

This module provides:
- AppConfig model for environment variable configuration with AUDIOCORE_ prefix
- VADConfig model for Voice Activity Detection parameters
- TOML configuration file loader with error handling and path expansion
- Configuration merger with priority chain (CLI > ENV > TOML > defaults)
"""

from audiocore.config.merger import load_config
from audiocore.config.settings import AppConfig
from audiocore.config.toml_loader import DEFAULT_CONFIG_PATH, load_toml_config
from audiocore.vad.config import VADConfig

__all__ = ["AppConfig", "DEFAULT_CONFIG_PATH", "VADConfig", "load_config", "load_toml_config"]
