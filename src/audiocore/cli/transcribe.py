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
import os
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

from audiocore.config import AppConfig, load_config
from audiocore.errors import (
    AudioCoreError,
    BackendError,
    ConfigurationError,
    OutputDirectoryError,
    OutputFileExistsError,
)
from audiocore.models import (
    TranscriptionOptions,
    TranscriptionResult,
    transcription_options_from_config,
)
from audiocore.output.file_writer import OutputFileConfig, format_and_write
from audiocore.parallel import FileResult, transcribe_files_concurrent
from audiocore.pipeline import Pipeline
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

if TYPE_CHECKING:
    from audiocore.pipeline.progress import PipelineStage

app = typer.Typer(help="Transcribe audio/video files")

# CLI exit codes (see the transcribe command docstring for the full contract).
_EXIT_INPUT_ERROR = 1
_EXIT_CONFIG_ERROR = 2
_EXIT_PROCESSING_ERROR = 3
_EXIT_BACKEND_ERROR = 4
_EXIT_OUTPUT_ERROR = 5


def parse_backend_type(value: str | None) -> BackendType | None:
    """Parse backend type from string.

    Args:
        value: String value from CLI

    Returns:
        BackendType enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    if value is None:
        return None
    try:
        return BackendType.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in BackendType)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


def parse_model_size(value: str | None) -> ModelSize | None:
    """Parse model size from string.

    Args:
        value: String value from CLI

    Returns:
        ModelSize enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    if value is None:
        return None
    try:
        return ModelSize.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in ModelSize)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


def parse_output_format(value: str | None) -> OutputFormat | None:
    """Parse output format from string.

    Args:
        value: String value from CLI

    Returns:
        OutputFormat enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    if value is None:
        return None
    try:
        return OutputFormat.parse(value)
    except ValueError as e:
        valid_options = ", ".join(f"'{m.value}'" for m in OutputFormat)
        raise typer.BadParameter(f"{e}. Valid options: {valid_options}") from e


def parse_selection_policy(value: str | None) -> SelectionPolicy | None:
    """Parse selection policy from string.

    Args:
        value: String value from CLI

    Returns:
        SelectionPolicy enum value

    Raises:
        typer.BadParameter: If value is invalid
    """
    if value is None:
        return None
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
        elif not os.access(file_path, os.R_OK):
            invalid_files.append(f"'{file_path}' is not readable")

    if invalid_files:
        raise typer.BadParameter(f"Invalid input files: {', '.join(invalid_files)}")

    return files


def _build_transcription_options(
    config: AppConfig,
    *,
    backend: str | BackendType | None,
    model: str | ModelSize | None,
    output_format: str | OutputFormat | None,
    backend_preference: str | SelectionPolicy | None,
    language: str | None,
    strict_vad: bool,
) -> TranscriptionOptions:
    """Resolve CLI override values into TranscriptionOptions.

    Omitted options stay implicit so backend-specific config (e.g. the
    default model) is still respected. Values may already be parsed enums
    when a typer callback ran, or raw strings otherwise.
    """
    backend_override = None
    if backend is not None:
        backend_override = (
            backend if isinstance(backend, BackendType) else BackendType.parse(backend)
        )

    model_override = None
    if model is not None:
        model_override = model if isinstance(model, ModelSize) else ModelSize.parse(model)

    output_format_override = None
    if output_format is not None:
        output_format_override = (
            output_format
            if isinstance(output_format, OutputFormat)
            else OutputFormat.parse(output_format)
        )

    backend_preference_override = None
    if backend_preference is not None:
        backend_preference_override = (
            backend_preference
            if isinstance(backend_preference, SelectionPolicy)
            else SelectionPolicy.parse(backend_preference)
        )

    options = transcription_options_from_config(
        config,
        language=language,
        model_size=model_override,
        backend=backend_override,
        output_format=output_format_override,
        backend_preference=backend_preference_override,
    )
    if strict_vad:
        options = options.model_copy(update={"strict_vad": True})
    return options


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
        str | None,
        typer.Option(
            "--format",
            "-f",
            help="Output format: text, json, srt, vtt",
            callback=parse_output_format,
        ),
    ] = None,
    backend: Annotated[
        str | None,
        typer.Option(
            "--backend",
            "-b",
            help="Backend to use: openai, faster_whisper, auto (default)",
            callback=parse_backend_type,
        ),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            "-l",
            help="Language code (e.g., 'en', 'es', 'fr')",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model size: tiny, base, small, medium, large",
            callback=parse_model_size,
        ),
    ] = None,
    backend_preference: Annotated[
        str | None,
        typer.Option(
            "--prefer",
            "-p",
            help="Backend preference: auto, prefer_local, prefer_cloud",
            callback=parse_selection_policy,
        ),
    ] = None,
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
    parallel: Annotated[
        bool,
        typer.Option(
            "--parallel",
            help="Enable batch mode for multiple input files. Multiple inputs already use batch mode.",
        ),
    ] = False,
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
    strict_vad: Annotated[
        bool,
        typer.Option(
            "--strict-vad",
            help="Fail if VAD processing fails instead of falling back to whole-file transcription.",
        ),
    ] = False,
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

    try:
        config = load_config()
    except ConfigurationError as e:
        console.print(f"[red]Configuration Error:[/red] {e}")
        raise typer.Exit(2) from None

    options = _build_transcription_options(
        config,
        backend=backend,
        model=model,
        output_format=output_format,
        backend_preference=backend_preference,
        language=language,
        strict_vad=strict_vad,
    )

    # Determine batch mode
    is_batch_mode = len(input_files) > 1 or (parallel and len(input_files) > 1)

    if is_batch_mode:
        # Batch mode: process multiple files concurrently
        exit_code = _run_batch_transcription(
            console=console,
            input_files=input_files,
            options=options,
            output_dir=output_dir,
            output_format=options.output_format,
            max_workers=max_workers,
            config=config,
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
            output_format=options.output_format,
            config=config,
        )

    if exit_code != 0:
        raise typer.Exit(exit_code)


def _exit_code_for_audiocore_error(console: Console, error: AudioCoreError) -> int:
    """Print a categorized error message and return its documented CLI exit code."""
    if isinstance(error, ConfigurationError):
        console.print(f"[red]Configuration Error:[/red] {error}")
        return _EXIT_CONFIG_ERROR
    if isinstance(error, BackendError):
        console.print(f"[red]Backend Error:[/red] {error}")
        return _EXIT_BACKEND_ERROR
    if isinstance(error, (OutputDirectoryError, OutputFileExistsError)):
        console.print(f"[red]Output Error:[/red] {error}")
        return _EXIT_OUTPUT_ERROR
    console.print(f"[red]Processing Error:[/red] {error}")
    return _EXIT_PROCESSING_ERROR


def _print_transcription_result(console: Console, result: TranscriptionResult) -> None:
    """Print formatted output, or fall back to timestamped segment lines."""
    if result.formatted_output:
        console.print(result.formatted_output)
        return
    for segment in result.segments:
        console.print(f"[{segment.start_time:.3f} - {segment.end_time:.3f}] {segment.text}")


def _transcribe_with_progress(
    console: Console,
    config: AppConfig,
    input_file: Path,
    options: TranscriptionOptions,
) -> TranscriptionResult:
    """Run the pipeline for one file behind a rich progress bar."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress_bar:
        task = progress_bar.add_task("[cyan]Initializing[/cyan]", total=100)
        pipeline = Pipeline(config=config)

        def update_progress(stage: PipelineStage, p: float, msg: str) -> None:
            progress_bar.update(
                task,
                completed=int(p * 100),
                description=f"[cyan]{stage.value}[/cyan] - {msg}",
            )

        result = pipeline.transcribe(
            path=input_file,
            options=options,
            progress_callback=update_progress,
        )
        progress_bar.update(task, completed=100)
    return result


def _emit_batch_result(
    console: Console,
    result: FileResult,
    output_dir: Path | None,
    output_format: OutputFormat,
    options: TranscriptionOptions,
    file_config: OutputFileConfig,
) -> bool:
    """Write or print one batch result; return True if the file failed."""
    if not (result.success and result.result):
        console.print(f"[red]✗[/red] {result.path.name}: {result.error}")
        return True
    if output_dir:
        output_path = output_dir / result.path.with_suffix(f".{output_format.value}").name
        format_and_write(result.result, options, output_path, file_config)
        console.print(f"[green]✓[/green] {result.path.name} -> {output_path}")
    else:
        console.print(f"\n[green]--- {result.path.name} ---[/green]")
        _print_transcription_result(console, result.result)
    return False


def _run_single_transcription(
    console: Console,
    input_file: Path,
    options: TranscriptionOptions,
    output_path: Path | None,
    output_dir: Path | None,
    output_format: OutputFormat,
    config: AppConfig,
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

    exit_code = 0
    try:
        result = _transcribe_with_progress(console, config, input_file, options)

        if final_output_path:
            file_config = OutputFileConfig(overwrite=True, create_dirs=True)
            format_and_write(result, options, final_output_path, file_config)
            console.print(f"[green]✓[/green] Transcription saved to: {final_output_path}")
        else:
            _print_transcription_result(console, result)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] File not found: {e}")
        exit_code = _EXIT_INPUT_ERROR
    except PermissionError as e:
        console.print(f"[red]Error:[/red] Permission denied: {e}")
        exit_code = _EXIT_INPUT_ERROR
    except AudioCoreError as e:
        exit_code = _exit_code_for_audiocore_error(console, e)

    return exit_code


def _run_batch_transcription(
    console: Console,
    input_files: list[Path],
    options: TranscriptionOptions,
    output_dir: Path | None,
    output_format: OutputFormat,
    max_workers: int,
    config: AppConfig,
) -> int:
    """Run transcription for multiple files concurrently.

    Args:
        console: Rich console for output
        input_files: List of input file paths
        options: Transcription options
        output_dir: Optional output directory
        output_format: Output format
        max_workers: Maximum concurrent workers
        config: Application configuration to use for all transcriptions

    Returns:
        Exit code (0 for all success, 1 for any failure)
    """
    total_files = len(input_files)
    failed_count = 0

    def progress_callback(completed: int, total: int, current_path: Path) -> None:
        """Update batch progress."""

    console.print(f"[cyan]Processing {total_files} file(s) with {max_workers} workers...[/cyan]")

    async def run_batch() -> list[FileResult]:
        """Run batch transcription asynchronously."""
        return await transcribe_files_concurrent(
            files=input_files,
            options=options,
            max_workers=max_workers,
            continue_on_error=True,
            progress_callback=progress_callback,
            config=config,
        )

    try:
        results_list = asyncio.run(run_batch())

        file_config = OutputFileConfig(overwrite=True, create_dirs=True)
        for result in results_list:
            if _emit_batch_result(console, result, output_dir, output_format, options, file_config):
                failed_count += 1

        success_count = total_files - failed_count
        if failed_count > 0:
            console.print(
                f"\n[yellow]Completed: {success_count}/{total_files} files "
                f"({failed_count} failed)[/yellow]"
            )
            return 1
        console.print(f"\n[green]✓ All {total_files} files transcribed successfully[/green]")
        return 0

    except AudioCoreError as e:
        return _exit_code_for_audiocore_error(console, e)


if __name__ == "__main__":
    app()
