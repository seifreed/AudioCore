"""Backend management commands for AudioCore CLI.

This module provides the 'audiocore backends' subcommands for listing
and checking backend availability.

Example:
    >>> # List all backends
    >>> audiocore backends list

    >>> # Check backend availability
    >>> audiocore backends check
"""

import typer
from rich.console import Console
from rich.table import Table

from audiocore.backends.availability import BackendAvailabilityChecker
from audiocore.config.merger import load_config
from audiocore.errors import ConfigurationError

app = typer.Typer(help="Manage and check backend availability")
console = Console()


def _load_config_or_exit():
    """Load configuration for backend commands, exiting cleanly on config errors."""
    try:
        return load_config()
    except ConfigurationError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(2) from None


@app.command("list")
def list_backends() -> None:
    """List all available backends with their status.

    Shows a table of all configured backends and whether they are
    available for use.

    Example:
        >>> audiocore backends list
    """
    config = _load_config_or_exit()
    checker = BackendAvailabilityChecker(config)

    statuses = checker.check_all()

    # Create table
    table = Table(title="Available Backends")
    table.add_column("Backend", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    for status in statuses:
        # Format status with color
        if status.available:
            status_str = "[green]✓ Available[/green]"
        else:
            status_str = "[red]✗ Unavailable[/red]"

        # Format details
        if status.reason:
            details = status.reason
            if status.suggestion:
                details += f"\n[dim]Suggestion: {status.suggestion}[/dim]"
        else:
            details = ""

        table.add_row(status.backend_type.value, status_str, details)

    console.print(table)


@app.command("check")
def check_backends() -> None:
    """Check if at least one backend is available.

    Validates backend configuration and exits with:
    - Exit code 0: At least one backend is available
    - Exit code 1: No backends are available

    Example:
        >>> audiocore backends check
        >>> echo $?  # 0 if available, 1 if not
    """
    config = _load_config_or_exit()
    checker = BackendAvailabilityChecker(config)

    statuses = checker.check_all()
    available = [s for s in statuses if s.available]

    if available:
        console.print("[green]✓[/green] Backend(s) available:")
        for status in available:
            console.print(f"  - {status.backend_type.value}")
        raise typer.Exit(0)
    else:
        console.print("[red]✗[/red] No backends available")
        console.print("\nTo configure backends:")
        console.print("  - OpenAI: Set OPENAI_API_KEY environment variable")
        console.print("  - Faster Whisper: Install with [cyan]pip install faster-whisper[/cyan]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
