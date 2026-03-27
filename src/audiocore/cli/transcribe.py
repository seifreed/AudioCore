"""Transcribe command for AudioCore CLI.

This module provides the 'audiocore transcribe' subcommand for transcribing
audio/video files with various options and progress display.

Example:
    >>> # Transcribe single file to stdout
    >>> # audiocore transcribe audio.mp3

    >>> # Transcribe to file with specific backend
    >>> # audiocore transcribe audio.mp3 --output result.txt --backend openai

    >>> # Transcribe multiple files concurrently
    >>> # audiocore transcribe file1.mp3 file2.mp3 --max-workers 4

    >>> # Transcribe with specific model and language
    >>> # audiocore transcribe audio.mp3 --model small --language en
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from audiocore.errors import AudioCoreError
from audiocore.models import TranscriptionOptions
from audiocore.parallel import FileResult, transcribe_files_concurrent
from audiocore.pipeline import Pipeline
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

if TYPE_CHECKING:
    from audiocore.pipeline.progress import PipelineStage

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


def validate_input_files(files: list[Path]) -> list[Path]:
    """Validate input files exist and are readable.

    Args:
        files: List of file paths to validate

    Returns:
        List of validated file paths

    Raises:
        typer.BadParameter: If any file is invalid
    """
    invalid_files = []
    for file_path in files:
        if not file_path.exists():
            invalid_files.append(f"'{file_path}' does not exist")
        elif not file_path.is_file():
            invalid_files.append(f"'{file_path}' is not a file")
        elif not file_path.exists() and file_path.exists():
            invalid_files.append(f"'{file_path}' is not readable")

    if invalid_files:
        raise typer.BadParameter(f"Invalid input files: {', '.join(invalid_files)}")

    return files


@app.command()
def transcribe(
    input_files: Annotated[
        list[Path],
        typer.Argument(
            ...,
            help="Path(s) to the audio/video file(s) to transcribe. Multiple files enable batch mode.",
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path. If not specified, prints to stdout. In batch mode, ignored.",
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
        str | None,
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
        Path | None,
        typer.Option(
            "--output-dir",
            "-d",
            help="Output directory for batch mode. Files saved with input filename + format extension.",
            exists=False,  # Will be created if needed
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    max_workers: Annotated[
        int,
        typer.Option(
            "--max-workers",
            "-w",
            help="Maximum concurrent workers for batch processing. Default: 4",
            min=1,
            max=32,
        ),
    ] = 4,
) -> None:
    """Transcribe one or more audio/video files.

    Transcribes audio/video file(s) using the configured backend.
    Single file: outputs to file or stdout.
    Multiple files: batch mode with concurrent processing.

    Exit codes:
        0: Success (all files in batch mode)
        1: Input file error / partial failure in batch mode
        2: Configuration error
        3: Processing error
        4: Backend unavailable
        5: Output error

    Example:
        >>> # Transcribe single file to stdout
        >>> audiocore transcribe podcast.mp3

        >>> # Transcribe to file with specific format
        >>> audiocore transcribe video.mp4 --output subtitles.srt --format srt

        >>> # Batch transcribe multiple files
        >>> audiocore transcribe file1.mp3 file2.mp3 file3.mp3 --output-dir ./output

        >>> # Batch transcribe with limited concurrency
        >>> audiocore transcribe *.mp3 --max-workers 2 --output-dir ./transcripts

        >>> # Use OpenAI backend
        >>> audiocore transcribe audio.mp3 --backend openai --language en
    """
    console = Console()

    # Validate input files
    try:
        input_files = validate_input_files(input_files)
    except typer.BadParameter as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None

    # Build transcription options
    options = TranscriptionOptions(
        language=language,
        model_size=model if isinstance(model, ModelSize) else ModelSize.parse(model),
        backend=(backend if isinstance(backend, BackendType) else BackendType.parse(backend)),
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

    # Determine batch mode
    is_batch_mode = len(input_files) > 1

    if is_batch_mode:
        # Batch mode: process multiple files concurrently
        exit_code = _run_batch_transcription(
            console=console,
            input_files=input_files,
            options=options,
            output_dir=output_dir,
            output_format=(
                output_format
                if isinstance(output_format, OutputFormat)
                else OutputFormat.parse(output_format)
            ),
            max_workers=max_workers,
        )
    else:
        # Single file mode
        input_file = input_files[0]
        exit_code = _run_single_transcription(
            console=console,
            input_file=input_file,
            options=options,
            output_path=output,
            output_dir=output_dir,
            output_format=(
                output_format
                if isinstance(output_format, OutputFormat)
                else OutputFormat.parse(output_format)
            ),
        )

    if exit_code != 0:
        raise typer.Exit(exit_code)


def _run_single_transcription(
    console: Console,
    input_file: Path,
    options: TranscriptionOptions,
    output_path: Path | None,
    output_dir: Path | None,
    output_format: OutputFormat,
) -> int:
    """Run transcription for a single file.

    Args:
        console: Rich console for output
        input_file: Path to input file
        options: Transcription options
        output_path: Optional output file path
        output_dir: Optional output directory
        output_format: Output format

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Determine output path
    if output_path:
        final_output_path = output_path
    elif output_dir:
        # Generate output filename based on input
        final_output_path = output_dir / input_file.with_suffix(f".{output_format.value}").name
    else:
        final_output_path = None

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
        ) as progress_bar:
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
        if final_output_path:
            # Write to file using format_and_write
            from audiocore.output.file_writer import OutputFileConfig, format_and_write

            file_config = OutputFileConfig(overwrite=True, create_dirs=True)
            format_and_write(result, options, final_output_path, file_config)
            console.print(f"[green]✓[/green] Transcription saved to: {final_output_path}")
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

    return exit_code


def _run_batch_transcription(
    console: Console,
    input_files: list[Path],
    options: TranscriptionOptions,
    output_dir: Path | None,
    output_format: OutputFormat,
    max_workers: int,
) -> int:
    """Run transcription for multiple files concurrently.

    Args:
        console: Rich console for output
        input_files: List of input file paths
        options: Transcription options
        output_dir: Optional output directory
        output_format: Output format
        max_workers: Maximum concurrent workers

    Returns:
        Exit code (0 for all success, 1 for any failure)
    """
    from audiocore.output.file_writer import OutputFileConfig, format_and_write

    total_files = len(input_files)
    completed_count = 0
    failed_count = 0
    results_list: list[FileResult] = []

    def progress_callback(completed: int, total: int, current_path: Path) -> None:
        """Update batch progress."""
        nonlocal completed_count
        completed_count = completed

    console.print(f"[cyan]Processing {total_files} file(s) with {max_workers} workers...[/cyan]")

    async def run_batch() -> list[FileResult]:
        """Run batch transcription asynchronously."""
        return await transcribe_files_concurrent(
            files=input_files,
            options=options,
            max_workers=max_workers,
            continue_on_error=True,
            progress_callback=progress_callback,
        )

    try:
        # Run async batch transcription
        results_list = asyncio.run(run_batch())

        # Process results and write outputs
        file_config = OutputFileConfig(overwrite=True, create_dirs=True)

        for result in results_list:
            if result.success and result.result:
                # Determine output path
                if output_dir:
                    output_path = (
                        output_dir / result.path.with_suffix(f".{output_format.value}").name
                    )
                    format_and_write(result.result, options, output_path, file_config)
                    console.print(f"[green]✓[/green] {result.path.name} -> {output_path}")
                else:
                    # Print to console
                    console.print(f"\n[green]--- {result.path.name} ---[/green]")
                    if result.result.formatted_output:
                        console.print(result.result.formatted_output)
                    else:
                        for segment in result.result.segments:
                            console.print(
                                f"[{segment.start_time:.3f} - {segment.end_time:.3f}] {segment.text}"
                            )
            else:
                failed_count += 1
                console.print(f"[red]✗[/red] {result.path.name}: {result.error}")

        # Summary
        success_count = total_files - failed_count
        if failed_count > 0:
            console.print(
                f"\n[yellow]Completed: {success_count}/{total_files} files "
                f"({failed_count} failed)[/yellow]"
            )
            return 1
        else:
            console.print(f"\n[green]✓ All {total_files} files transcribed successfully[/green]")
            return 0

    except AudioCoreError as e:
        if "config" in str(e).lower():
            console.print(f"[red]Configuration Error:[/red] {e}")
            return 2
        elif "backend" in str(e).lower():
            console.print(f"[red]Backend Error:[/red] {e}")
            return 4
        else:
            console.print(f"[red]Processing Error:[/red] {e}")
            return 3


if __name__ == "__main__":
    app()
