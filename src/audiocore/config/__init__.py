"""Configuration module for AudioCore.

This module provides:
- AppConfig model for environment variable configuration with AUDIOCORE_ prefix
- TOML configuration file loader with error handling and path expansion
"""

from audiocore.config.settings import AppConfig
from audiocore.config.toml_loader import DEFAULT_CONFIG_PATH, load_toml_config

__all__ = ["AppConfig", "DEFAULT_CONFIG_PATH", "load_toml_config"]
