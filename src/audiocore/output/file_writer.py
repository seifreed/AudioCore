"""File output utilities with atomic writing and directory creation.

Provides utilities for writing transcription output to files with:
- Atomic write pattern (temp file → move)
- Automatic parent directory creation
- Overwrite protection for existing files
- Support for writing to stdout (path=None)

Example:
    >>> from audiocore.output.file_writer import write_output, OutputFileConfig
    >>> from pathlib import Path
    >>> config = OutputFileConfig(overwrite=False, create_dirs=True)
    >>> write_output("Hello world", Path("output/result.txt"), config)
    PosixPath('output/result.txt')
"""

from __future__ import annotations

import codecs
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from audiocore.errors.output import OutputDirectoryError, OutputFileExistsError
from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult
from audiocore.output.json import format_json
from audiocore.output.srt import format_srt
from audiocore.output.text import format_text
from audiocore.output.vtt import format_vtt
from audiocore.types.format import OutputFormat


class OutputFileConfig(BaseModel):
    """Configuration for file output writing.

    Attributes:
        overwrite: If True, replace existing files. If False, raise error on existing file.
        create_dirs: If True, create parent directories if they don't exist.
        encoding: Text encoding for file writing (default: utf-8).
    """

    model_config = {"strict": True, "extra": "forbid"}

    overwrite: bool = Field(default=False, description="Replace existing files if True")
    create_dirs: bool = Field(
        default=True, description="Create parent directories if they don't exist"
    )
    encoding: str = Field(default="utf-8", description="Text encoding for file writing")

    @field_validator("encoding")
    @classmethod
    def validate_encoding(cls, value: str) -> str:
        """Normalize and validate text encoding names."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("encoding must not be empty")
        try:
            codecs.lookup(normalized)
        except LookupError as e:
            raise ValueError(f"Unknown encoding: {value}") from e
        return normalized


def write_output(
    content: str,
    path: Path | str | None,
    config: OutputFileConfig | None = None,
) -> Path | None:
    """Write content to a file with atomic write pattern.

    Uses atomic write pattern: write to temp file, then move (atomic on most systems).
    Creates parent directories automatically if create_dirs=True.
    Raises OutputFileExistsError if file exists and overwrite=False.

    Args:
        content: Text content to write to file.
        path: Output file path. If None, writes to stdout and returns None.
        config: Output configuration. If None, uses defaults (overwrite=False, create_dirs=True).

    Returns:
        Path to written file, or None if path=None (stdout).

    Raises:
        OutputFileExistsError: If file exists and overwrite=False.
        OSError: If directory creation fails or write fails.

    Example:
        >>> write_output("Hello world", "output/result.txt")
        PosixPath('output/result.txt')
        >>> write_output("Hello", None)  # Writes to stdout
        None
    """
    # Use default config if not provided
    if config is None:
        config = OutputFileConfig()

    # Handle stdout case
    if path is None:
        sys.stdout.write(content)
        return None

    file_path = Path(path) if isinstance(path, str) else path
    _validate_output_path(file_path, config)
    _atomic_write(file_path, content, config)
    return file_path


def _validate_output_path(file_path: Path, config: OutputFileConfig) -> None:
    """Validate the destination path and overwrite/create-dirs policy.

    Raises:
        OutputDirectoryError: If the path is a directory or the parent is
            invalid/missing when create_dirs is disabled.
        OutputFileExistsError: If the file exists and overwrite is disabled.
    """
    if file_path.exists() and file_path.is_dir():
        raise OutputDirectoryError(
            f"Output path is not a file: {file_path}",
            context={"file_path": str(file_path)},
            suggestions=[
                "Choose a file path inside the directory",
                "Provide an output filename with an extension",
            ],
        )

    if file_path.parent and file_path.parent.exists() and not file_path.parent.is_dir():
        raise OutputDirectoryError(
            f"Parent path is not a directory: {file_path.parent}",
            context={"file_path": str(file_path), "parent_dir": str(file_path.parent)},
            suggestions=[
                "Choose a different output path",
                "Remove or rename the parent file blocking directory creation",
            ],
        )

    if not config.create_dirs and file_path.parent and not file_path.parent.exists():
        raise OutputDirectoryError(
            f"Parent directory does not exist: {file_path.parent}",
            context={"file_path": str(file_path), "parent_dir": str(file_path.parent)},
            suggestions=[
                "Set create_dirs=True to auto-create parent directories",
                f"Create directory: mkdir -p {file_path.parent}",
            ],
        )

    if file_path.exists() and not config.overwrite:
        raise OutputFileExistsError(
            f"Output file already exists: {file_path}",
            context={"file_path": str(file_path)},
            suggestions=[
                "Set overwrite=True to replace existing file",
                "Choose a different output path",
            ],
        )


def _atomic_write(file_path: Path, content: str, config: OutputFileConfig) -> None:
    """Write content via a temp file in the same directory, then atomic-replace.

    Creates parent directories first when create_dirs is set. A failed write
    leaves no partial output: the temp file is removed before re-raising.
    """
    if config.create_dirs and file_path.parent:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file on the same filesystem so the move is atomic.
    parent_dir = file_path.parent if file_path.parent.exists() else Path.cwd()
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=config.encoding,
            suffix=".tmp",
            dir=parent_dir,
            delete=False,
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            temp_path = Path(temp_file.name)

        temp_path.replace(file_path)
    except Exception:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
        raise


# Mapping of OutputFormat to formatter function
_FORMATTERS: dict[OutputFormat, Callable[[TranscriptionResult, TranscriptionOptions], str]] = {
    OutputFormat.TEXT: format_text,
    OutputFormat.JSON: format_json,
    OutputFormat.SRT: format_srt,
    OutputFormat.VTT: format_vtt,
}


def format_and_write(
    result: TranscriptionResult,
    options: TranscriptionOptions,
    path: Path | str | None,
    config: OutputFileConfig | None = None,
) -> Path | None:
    """Format transcription result and write to file.

    Auto-detects output format from file extension and uses appropriate formatter.
    Falls back to options.output_format if extension is unknown.

    Args:
        result: TranscriptionResult containing segments and metadata.
        options: TranscriptionOptions with output_format as fallback.
        path: Output file path. If None, writes to stdout and returns None.
            Extension is used to determine format (.txt, .json, .srt, .vtt).
        config: Output configuration. If None, uses defaults.

    Returns:
        Path to written file, or None if path=None (stdout).

    Raises:
        OutputFileExistsError: If file exists and overwrite=False.
        OSError: If directory creation fails or write fails.

    Example:
        >>> from audiocore.models import TranscriptionResult, TranscriptionOptions
        >>> result = TranscriptionResult(...)
        >>> format_and_write(result, TranscriptionOptions(), "output.srt")
        PosixPath('output.srt')

    Note:
        For stdout (path=None), uses options.output_format to determine format,
        defaulting to TEXT if not specified.
    """
    # Determine format from extension or options
    output_format: OutputFormat

    if path is not None:
        # Auto-detect format from file extension
        file_path = Path(path) if isinstance(path, str) else path
        extension = file_path.suffix.lower().lstrip(".")

        try:
            output_format = OutputFormat.parse(extension)
        except ValueError:
            # Unknown extension, use options.output_format
            output_format = options.output_format
    else:
        # No path (stdout), use options.output_format
        output_format = options.output_format

    # Get formatter and format content
    formatter = _FORMATTERS[output_format]
    content = formatter(result, options)

    # Write using write_output
    return write_output(content, path, config)
