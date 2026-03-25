"""Transcribe command for AudioCore CLI.

This module provides the 'audiocore transcribe' subcommand for transcribing
audio/video files with various options and progress display.

Example:
    >>> # Transcribe to stdout
    >>> # audiocore transcribe audio.mp3

    >>> # Transcribe to file with specific backend
    >>> # audiocore transcribe audio.mp3 --output result.txt --backend openai

    >>> # Transcribe with specific model and language
    >>> # audiocore transcribe audio.mp3 --model small --language en
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from audiocore.config import AppConfig
from audiocore.errors import AudioCoreError
from audiocore.models import TranscriptionOptions
from audiocore.pipeline import Pipeline
from audiocore.pipeline.progress import PipelineStage
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

app = typer.Typer(help="Transcribe audio/video files")


def parse_backend_type(value: str) -> BackendType:
    """Parse backend type from string.

    Args:
        value: String value from CLI

    Returns:
        BackendType enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    try:
        return BackendType.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in BackendType if m != BackendType.AUTO)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


def parse_model_size(value: str) -> ModelSize:
    """Parse model size from string.

    Args:
        value: String value from CLI

    Returns:
        ModelSize enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    try:
        return ModelSize.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in ModelSize)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


def parse_output_format(value: str) -> OutputFormat:
    """Parse output format from string.

    Args:
        value: String value from CLI

    Returns:
        OutputFormat enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    try:
        return OutputFormat.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in OutputFormat)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


def parse_selection_policy(value: str) -> SelectionPolicy:
    """Parse selection policy from string.

    Args:
        value: String value from CLI

    Returns:
        SelectionPolicy enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    try:
        return SelectionPolicy.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in SelectionPolicy)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


@app.command()
def transcribe(
    input_file: Annotated[
        Path,
        typer.Argument(
            ...,
            help="Path to the audio/video file to transcribe",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Output file path. If not specified, prints to stdout",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: text, json, srt, vtt",
            callback=lambda v: parse_output_format(v) if v else None,
        ),
    ] = "text",
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            "-b",
            help="Backend to use: openai, faster_whisper, auto (default)",
            callback=lambda v: parse_backend_type(v) if v else None,
        ),
    ] = "auto",
    language: Annotated[
        Optional[str],
        typer.Option(
            "--language",
            "-l",
            help="Language code (e.g., 'en', 'es', 'fr')",
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model size: tiny, base, small, medium, large",
            callback=lambda v: parse_model_size(v) if v else None,
        ),
    ] = "base",
    backend_preference: Annotated[
        str,
        typer.Option(
            "--prefer",
            "-p",
            help="Backend preference: auto, prefer_local, prefer_cloud",
            callback=lambda v: parse_selection_policy(v) if v else None,
        ),
    ] = "auto",
    output_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--output-dir",
            "-d",
            help="Output directory (used when --format determines filename)",
            exists=False,  # Will be created if needed
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
) -> None:
    """Transcribe an audio/video file.

    Transcribes the given audio/video file using the configured backend
    and outputs the result to a file or stdout.

    Exit codes:
        0: Success
        1: Input file error
        2: Configuration error
        3: Processing error
        4: Backend unavailable
        5: Output error

    Example:
        >>> # Transcribe to stdout
        >>> audiocore transcribe podcast.mp3

        >>> # Transcribe to file with specific format
        >>> audiocore transcribe video.mp4 --output subtitles.srt --format srt

        >>> # Use OpenAI backend
        >>> audiocore transcribe audio.mp3 --backend openai --language en
    """  # noqa: D401
    from rich.console import Console

    console = Console()

    # Build transcription options
    options = TranscriptionOptions(
        language=language,
        model_size=model if isinstance(model, ModelSize) else ModelSize.parse(model),
        backend=backend if isinstance(backend, BackendType) else BackendType.parse(backend),
        output_format=(
            output_format
            if isinstance(output_format, OutputFormat)
            else OutputFormat.parse(output_format)
        ),
        backend_preference=(
            backend_preference
            if isinstance(backend_preference, SelectionPolicy)
            else SelectionPolicy.parse(backend_preference)
        ),
    )

    # Determine output path
    if output:
        output_path = output
    elif output_dir:
        # Generate output filename based on input
        output_path = output_dir / input_file.with_suffix(f".{output_format}").name
    else:
        output_path = None

    # Track current stage for progress display
    current_stage: list[str] = ["Initializing"]

    def progress_callback(stage: PipelineStage, progress: float, message: str) -> None:
        """Update progress display."""
        current_stage[0] = stage.value

    # Run transcription with progress display
    exit_code = 0

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress_bar:  # type: ignore[assignment]
            task = progress_bar.add_task(
                f"[cyan]{current_stage[0]}[/cyan]",
                total=100,
            )

            # Create pipeline
            pipeline = Pipeline()

            # Create progress callback that updates progress bar
            def update_progress(stage: PipelineStage, p: float, msg: str) -> None:
                progress_bar.update(
                    task,
                    completed=int(p * 100),
                    description=f"[cyan]{stage.value}[/cyan] - {msg}",
                )

            # Run transcription
            result = pipeline.transcribe(
                path=input_file,
                options=options,
                progress_callback=update_progress,
            )

            progress_bar.update(task, completed=100)

        # Output result
        if output_path:
            # Write to file using format_and_write
            from audiocore.output.file_writer import OutputFileConfig, format_and_write

            file_config = OutputFileConfig(overwrite=True, create_dirs=True)
            format_and_write(result, options, output_path, file_config)
            console.print(f"[green]✓[/green] Transcription saved to: {output_path}")
        else:
            # Print to stdout
            if result.formatted_output:
                console.print(result.formatted_output)
            else:
                # Fallback to segments
                for segment in result.segments:
                    console.print(
                        f"[{segment.start_time:.3f} - {segment.end_time:.3f}] {segment.text}"
                    )

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e}")
        exit_code = 1
    except PermissionError as e:
        console.print(f"[red]Error:[/red] Permission denied: {e}")
        exit_code = 1
    except AudioCoreError as e:
        if "config" in str(e).lower():
            console.print(f"[red]Configuration Error:[/red] {e}")
            exit_code = 2
        elif "backend" in str(e).lower():
            console.print(f"[red]Backend Error:[/red] {e}")
            exit_code = 4
        elif "format" in str(e).lower():
            console.print(f"[red]Output Error:[/red] {e}")
            exit_code = 5
        else:
            console.print(f"[red]Processing Error:[/red] {e}")
            exit_code = 3

    if exit_code != 0:
        raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
