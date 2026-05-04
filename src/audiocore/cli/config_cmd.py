"""Config display commands for AudioCore CLI.

This module provides the 'audiocore config' subcommands for displaying
configuration and config file location.

Example:
    >>> # Show configuration with redacted keys
    >>> audiocore config show

    >>> # Show config file path
    >>> audiocore config path
"""

import typer
from rich.console import Console
from rich.table import Table

from audiocore.config import load_config

app = typer.Typer(help="Display AudioCore configuration")
console = Console()


def mask_api_key(key: str | None) -> str:
    """Mask API key for display, showing only first 4 characters if long enough.

    Args:
        key: API key string

    Returns:
        Masked API key (e.g., "sk-***..." or "(not set)")
    """
    if not key:
        return "(not set)"

    # For OpenAI keys that start with "sk-"
    if key.startswith("sk-") and len(key) > 6:
        return f"sk-***...{key[-4:]}"

    # For other keys that are long enough
    if len(key) > 8:
        return f"{key[:4]}***...{key[-4:]}"

    # For short keys, just show asterisks
    return "***"


def mask_secret_str(secret: object) -> str:
    """Mask SecretStr for display.

    Args:
        secret: SecretStr value from config

    Returns:
        Masked string representation
    """
    from pydantic import SecretStr

    if secret is None:
        return "(not set)"

    if isinstance(secret, SecretStr):
        value = secret.get_secret_value()
        return mask_api_key(value)

    return str(secret)


@app.command("show")
def show_config() -> None:
    """Display current configuration with API keys redacted.

    Shows all configured settings with sensitive values masked.
    Configuration is loaded from environment variables and
    audiocore.toml file (if present).

    Example:
        >>> audiocore config show
    """
    try:
        config = load_config()
    except Exception as e:
        console.print("[red]Error:[/red] Failed to load configuration")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1) from None

    # Create table for config display
    table = Table(title="AudioCore Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    # Backend settings
    table.add_row("Backend", str(config.backend.value))
    table.add_row("Model", str(config.model.value))
    table.add_row("Language", config.language or "(auto-detect)")
    table.add_row("Output Format", str(config.output_format.value))
    table.add_row("Backend Preference", str(config.backend_preference.value))

    # Paths
    table.add_row("ffprobe Path", config.ffprobe_path)
    table.add_row("ffmpeg Path", config.ffmpeg_path)

    # OpenAI config
    if config.openai:
        api_key = mask_secret_str(config.openai.api_key)
        table.add_row("OpenAI API Key", api_key)
        if config.openai.organization:
            table.add_row("OpenAI Organization", config.openai.organization)
        table.add_row("OpenAI Timeout", f"{config.openai.timeout}s")
        table.add_row("OpenAI Max Retries", str(config.openai.max_retries))

    # VAD config
    if config.vad:
        table.add_row("VAD Min Segment Duration", f"{config.vad.min_segment_duration}s")
        table.add_row("VAD Max Segment Duration", f"{config.vad.max_segment_duration}s")
        table.add_row("VAD Speech Threshold", f"{config.vad.speech_threshold}")
        table.add_row("VAD Silence Threshold", f"{config.vad.silence_threshold}")

    console.print(table)


@app.command("path")
def config_path() -> None:
    """Display the default configuration file location.

    Shows where AudioCore looks for the audiocore.toml configuration file.
    The file is optional - if not present, defaults are used.

    Example:
        >>> audiocore config path
    """
    from audiocore.config.toml_loader import DEFAULT_CONFIG_PATH

    console.print("[cyan]Default configuration path:[/cyan]")
    path_obj = DEFAULT_CONFIG_PATH
    exists_str = "[green]✓ exists[/green]" if path_obj.exists() else "[dim](not found)[/dim]"
    console.print(f"  {path_obj} {exists_str}")

    console.print()
    console.print("[cyan]Priority:[/cyan]")
    console.print("  1. CLI arguments")
    console.print("  2. Environment variables (AUDIOCORE_*)")
    console.print("  3. audiocore.toml config file")
    console.print("  4. Default values")


if __name__ == "__main__":
    app()
