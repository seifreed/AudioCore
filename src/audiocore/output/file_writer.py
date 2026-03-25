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

import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from audiocore.errors.output import OutputFileExistsError


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

    # Convert to Path object
    file_path = Path(path) if isinstance(path, str) else path

    # Check for overwrite protection
    if file_path.exists() and not config.overwrite:
        raise OutputFileExistsError(
            f"Output file already exists: {file_path}",
            context={"file_path": str(file_path)},
            suggestions=[
                "Set overwrite=True to replace existing file",
                "Choose a different output path",
            ],
        )

    # Create parent directories if needed
    if config.create_dirs and file_path.parent:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then move (atomic on most systems)
    # Use same directory to ensure same filesystem for atomic move
    parent_dir = file_path.parent if file_path.parent.exists() else Path.cwd()
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

        # Atomic move (rename on Unix/Windows)
        temp_path.replace(file_path)
    except Exception:
        # Clean up temp file if write failed
        if "temp_path" in locals() and temp_path.exists():
            temp_path.unlink()
        raise

    return file_path
