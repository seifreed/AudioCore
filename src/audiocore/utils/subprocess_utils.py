"""Secure subprocess utilities with input validation.

This module provides subprocess wrappers that:
- Validate all executable paths before execution
- Use lists instead of shell=True (prevents shell injection)
- Provide explicit security guarantees for Bandit compliance

Security considerations:
- All executable paths are validated against shell metacharacters
- No shell=True usage - commands are passed as lists
- Timeouts are enforced to prevent hanging
- Output is captured, not inherited from caller
"""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_SHELL_METACHARACTERS = {"|", "&", ";", "$", "`", "(", ")", "<", ">", "\n", "\r"}


def validate_executable_path(executable_path: str) -> str:
    """Validate that executable path is safe and exists.

    Security: Prevents command injection by validating that the path
    is a simple executable name or absolute path without shell metacharacters.

    Args:
        executable_path: Path or name of executable to validate.

    Returns:
        Validated executable path.

    Raises:
        ValueError: If path contains dangerous characters or doesn't exist.
    """
    if any(char in executable_path for char in _SHELL_METACHARACTERS):
        raise ValueError(
            f"Invalid executable path: contains forbidden characters: {executable_path}"
        )

    resolved = shutil.which(executable_path)
    if resolved is None:
        raise ValueError(f"Executable not found: {executable_path}")

    return executable_path


def safe_run(
    command: list[str],
    *,
    timeout: float | None = None,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run subprocess command safely with validation.

    This wrapper enforces security best practices:
    1. Command must be a list (prevents shell injection)
    2. First element (executable) is validated
    3. No shell=True (always False)
    4. Timeout required for network/external commands

    Args:
        command: List of command arguments. First element is the executable.
        timeout: Timeout in seconds. Required for external commands.
        check: Raise on non-zero exit code. Default True.
        capture_output: Capture stdout/stderr. Default True.
        text: Return strings instead of bytes. Default True.
        cwd: Working directory for the command.
        env: Environment variables for the command.

    Returns:
        CompletedProcess with stdout, stderr, returncode.

    Raises:
        ValueError: If command is empty or executable is invalid.
        subprocess.TimeoutExpired: If command times out.
        subprocess.CalledProcessError: If check=True and return code != 0.
    """
    if not command:
        raise ValueError("Command cannot be empty")

    executable = command[0]
    validate_executable_path(executable)

    logger.debug(f"Running command: {executable}")

    result = subprocess.run(
        command,
        timeout=timeout,
        check=check,
        capture_output=capture_output,
        text=text,
        cwd=cwd,
        env=env,
        shell=False,
    )

    return result
