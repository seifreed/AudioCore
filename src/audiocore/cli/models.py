"""Model management commands for AudioCore CLI.

This module provides the 'audiocore models' subcommands for managing
faster-whisper models (list, download, remove).

Example:
    >>> # List models
    >>> audiocore models list

    >>> # Download a model
    >>> audiocore models download base

    >>> # Remove a model
    >>> audiocore models remove base
"""

from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from audiocore.backends.faster_whisper.model_manager import ModelManager
from audiocore.types.backend import ModelSize

app = typer.Typer(help="Manage faster-whisper models")
console = Console()


def parse_model_size(value: str) -> str:
    """Validate model size string.

    Args:
        value: Model size string from CLI

    Returns:
        Validated model size string

    Raises:
        typer.BadParameter: If model size is invalid
    """
    try:
        # Validate by parsing through ModelSize enum
        model_size = ModelSize.parse(value)
        return model_size.value
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in ModelSize)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


@app.command("list")
def list_models() -> None:
    """List all faster-whisper models with download status.

    Shows a table of all available model sizes and whether they are
    downloaded locally.

    Example:
        >>> audiocore models list
    """
    manager = ModelManager()
    models = manager.list_models()

    # Create table
    table = Table(title="Faster Whisper Models")
    table.add_column("Model", style="cyan")
    table.add_column("Size", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Path", style="dim")

    for model in models:
        # Format status with color
        if model.downloaded:
            status_str = "[green]✓ Downloaded[/green]"
            path_str = str(model.local_path) if model.local_path else ""
        else:
            status_str = "[yellow]Not downloaded[/yellow]"
            path_str = ""

        # Format size
        if model.size_mb >= 1000:
            size_str = f"{model.size_mb / 1000:.1f} GB"
        else:
            size_str = f"{model.size_mb} MB"

        table.add_row(model.name, size_str, status_str, path_str)

    console.print(table)


@app.command("download")
def download_model(
    model: Annotated[
        str,
        typer.Argument(
            ...,
            help="Model size to download (tiny, base, small, medium, large, large-v3, large-v3-turbo)",
            callback=parse_model_size,
        ),
    ],
) -> None:
    """Download a faster-whisper model from HuggingFace Hub.

    Downloads the specified model to the local cache if not already present.

    Example:
        >>> audiocore models download base
        >>> audiocore models download large-v3
    """
    manager = ModelManager()

    # Check if already downloaded
    if manager.is_model_downloaded(model):
        console.print(f"[yellow]Model '{model}' is already downloaded[/yellow]")
        path = manager.get_model_path(model)
        if path:
            console.print(f"[dim]Location: {path}[/dim]")
        raise typer.Exit(0)

    # Download with progress
    console.print(f"[cyan]Downloading model '{model}'...[/cyan]")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress_bar:
            task = progress_bar.add_task(f"Downloading {model}...", total=None)

            # Download (HuggingFace hub doesn't provide progress easily)
            path = manager.download_model(model, progress_callback=None)

            progress_bar.update(task, completed=True, description=f"Downloaded {model}")

        console.print(f"[green]✓[/green] Model '{model}' downloaded successfully")
        console.print(f"[dim]Location: {path}[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to download model '{model}'")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1) from None


@app.command("remove")
def remove_model(
    model: Annotated[
        str,
        typer.Argument(
            ...,
            help="Model size to remove (tiny, base, small, medium, large, large-v3, large-v3-turbo)",
            callback=parse_model_size,
        ),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Remove a downloaded faster-whisper model from cache.

    Deletes the model from local cache to free up disk space.

    Example:
        >>> audiocore models remove base
        >>> audiocore models remove large-v3 --force
    """
    manager = ModelManager()

    # Check if downloaded
    if not manager.is_model_downloaded(model):
        console.print(f"[yellow]Model '{model}' is not downloaded[/yellow]")
        raise typer.Exit(0)

    # Confirm unless --force
    if not force:
        size_mb = None
        models = manager.list_models()
        for m in models:
            if m.name == model:
                size_mb = m.size_mb
                break

        size_str = (
            f"{size_mb} MB"
            if size_mb is not None and size_mb < 1000
            else (f"{size_mb / 1000:.1f} GB" if size_mb is not None and size_mb >= 1000 else "")
        )
        confirm = typer.confirm(
            f"Remove model '{model}' ({size_str})?",
            default=False,
        )
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Delete model
    try:
        manager.delete_model(model)
        console.print(f"[green]✓[/green] Model '{model}' removed successfully")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to remove model '{model}'")
        console.print(f"[dim]{e}[/dim]")
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
