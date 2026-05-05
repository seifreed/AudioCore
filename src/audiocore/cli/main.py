"""Main CLI entry point for AudioCore.

This module provides the main Typer app with subcommands for:
- transcribe: Transcribe audio/video files
- backends: Manage and check backends
- models: Manage faster-whisper models
- config: Display configuration

Example:
    >>> from audiocore.cli.main import app
    >>> # Use with typer CLI
    >>> # audiocore --help
    >>> # audiocore transcribe audio.mp3 --output result.txt
"""

import typer
from rich.console import Console

from audiocore.backends import register_builtin_backends

register_builtin_backends()

app = typer.Typer(
    name="audiocore",
    help="AudioCore - Audio/Video transcription engine with dual backend support",
    add_completion=False,
    rich_markup_mode="rich",
)

# Rich console for output
console = Console()


# Version callback
def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from audiocore import __version__

        console.print(f"audiocore version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """AudioCore - Audio/Video transcription engine with dual backend support.

    AudioCore bridges cloud and local transcription with automatic backend
    selection, handling audio extraction, VAD segmentation, and output
    formatting so developers don't have to.

    Use --help with any subcommand for detailed usage information.
    """


# Import and register subcommands
# Note: Imports are at end of file to avoid circular imports


def register_subcommands() -> None:
    """Register all CLI subcommands."""
    from audiocore.cli.backends import app as backends_app
    from audiocore.cli.config_cmd import app as config_app
    from audiocore.cli.models import app as models_app
    from audiocore.cli.transcribe import transcribe as transcribe_command

    app.command(name="transcribe")(transcribe_command)
    app.add_typer(backends_app, name="backends")
    app.add_typer(models_app, name="models")
    app.add_typer(config_app, name="config")


# Register subcommands when module is loaded
register_subcommands()
