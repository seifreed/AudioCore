"""CLI module for AudioCore command-line interface.

This module provides the main entry point for the audiocore CLI tool,
using Typer for argument parsing and Rich for progress display.
"""

from audiocore.cli.main import app

__all__ = ["app"]
