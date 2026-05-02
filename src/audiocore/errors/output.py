"""
Output-related exceptions.

These exceptions are raised when there are problems with output files
or writing results.
"""

from typing import Any

from audiocore.errors.base import AudioCoreError


class OutputFileExistsError(AudioCoreError):
    """
    Exception raised when output file already exists and overwrite is disabled.

    This is raised when:
    - Output file exists and overwrite=False
    - User needs to explicitly enable overwrite to replace existing files

    Example:
        >>> raise OutputFileExistsError(
        ...     "Output file already exists",
        ...     context={"file_path": "/path/to/output.srt"},
        ...     suggestions=["Set overwrite=True to replace existing file"]
        ... )
    """

    error_code: str = "AUD-600"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Add default suggestions if none provided
        if suggestions is None:
            suggestions = [
                "Set overwrite=True to replace existing file",
                "Choose a different output path",
            ]
        super().__init__(message, context, suggestions, cause)


class OutputDirectoryError(AudioCoreError):
    """
    Exception raised when the output directory does not exist and create_dirs is False.

    This is raised when:
    - Parent directory does not exist and create_dirs=False
    - User needs to enable directory creation or create the directory manually

    Example:
        >>> raise OutputDirectoryError(
        ...     "Parent directory does not exist",
        ...     context={"file_path": "/path/to/output.srt", "parent_dir": "/path/to"},
        ...     suggestions=["Set create_dirs=True to auto-create parent directories"]
        ... )
    """

    error_code: str = "AUD-601"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        # Add default suggestions if none provided
        if suggestions is None:
            suggestions = [
                "Set create_dirs=True to auto-create parent directories",
                "Create the directory manually",
            ]
        super().__init__(message, context, suggestions, cause)
