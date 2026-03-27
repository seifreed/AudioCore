"""Media probing utilities using ffprobe.

This module provides functions to extract metadata from audio/video files
using ffprobe (part of ffmpeg).
"""

import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from audiocore.errors import InvalidInputError, MediaError
from audiocore.models import MediaInfo
from audiocore.utils.subprocess_utils import safe_run


def _validate_file_exists(file_path: Path) -> None:
    """Validate that a file exists and is readable.

    Args:
        file_path: Path to the file to validate.

    Raises:
        InvalidInputError: If the file does not exist.
    """
    if not file_path.exists():
        raise InvalidInputError(
            f"File not found: {file_path}",
            context={"file_path": str(file_path)},
            suggestions=[
                "Verify the file path is correct",
                "Check file permissions",
                "Ensure the file exists",
            ],
        )


def _validate_executable_path(executable_path: str) -> str:
    """Validate that executable path is safe and exists.

    Security: Prevents command injection by validating that the path
    is a simple executable name or absolute path without shell metacharacters.

    Args:
        executable_path: Path or name of executable to validate.

    Returns:
        Validated executable path.

    Raises:
        MediaError: If path contains dangerous characters or doesn't exist.
    """
    dangerous_chars = {"|", "&", ";", "$", "`", "(", ")", "<", ">", "\n", "\r"}
    if any(char in executable_path for char in dangerous_chars):
        raise MediaError(
            "Invalid executable path: contains forbidden characters",
            context={"path": executable_path},
            suggestions=[
                "Use simple executable name (e.g., 'ffprobe')",
                "Use absolute path without special characters",
            ],
        )

    if shutil.which(executable_path) is None:
        raise MediaError(
            f"Executable not found: {executable_path}",
            context={"path": executable_path},
            suggestions=[
                "Install the required executable",
                "Verify the path is correct",
                f"Ensure {executable_path} is in PATH",
            ],
        )

    return executable_path


def probe(
    file_path: Path | str,
    ffprobe_path: str = "ffprobe",
    timeout: int = 30,
) -> MediaInfo:
    """Probe a media file for metadata using ffprobe.

    Extracts duration, format, codec, sample rate, and channel information
    from audio/video files.

    Args:
        file_path: Path to the media file to probe.
        ffprobe_path: Path to ffprobe executable. Defaults to "ffprobe".
        timeout: Timeout in seconds for ffprobe command. Defaults to 30.

    Returns:
        MediaInfo model with extracted metadata.

    Raises:
        InvalidInputError: If the file does not exist.
        MediaError: If ffprobe fails or returns invalid data.

    Example:
        >>> from pathlib import Path
        >>> from audiocore.media import probe
        >>> info = probe(Path("audio.mp3"))
        >>> info.duration
        180.5
        >>> info.format
        'mp3'
    """
    file_path = Path(file_path)
    _validate_file_exists(file_path)

    # Validate ffprobe executable path (security: prevent command injection)
    _validate_executable_path(ffprobe_path)

    # Build ffprobe command
    command = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]

    try:
        result = safe_run(
            command,
            timeout=timeout,
            check=False,  # We handle return code manually
        )
    except ValueError as e:
        raise MediaError(
            f"Invalid ffprobe path: {ffprobe_path}",
            context={"ffprobe_path": ffprobe_path, "file_path": str(file_path)},
            suggestions=[
                "Install ffmpeg (includes ffprobe)",
                f"Verify {ffprobe_path} is in PATH or provide full path",
                "Set AUDIOCORE_FFPROBE_PATH environment variable",
            ],
            cause=e,
        ) from e
    except subprocess.TimeoutExpired as e:
        raise MediaError(
            f"ffprobe timed out after {timeout} seconds",
            context={"timeout": timeout, "file_path": str(file_path)},
            suggestions=[
                f"Try increasing timeout (current: {timeout}s)",
                "Check if file is very large",
                "Verify ffprobe is responsive",
            ],
            cause=e,
        ) from e

    if result.returncode != 0:
        raise MediaError(
            f"ffprobe failed with return code {result.returncode}",
            context={
                "return_code": result.returncode,
                "stderr": result.stderr[:500] if result.stderr else None,
                "file_path": str(file_path),
            },
            suggestions=[
                "Check file format is supported",
                "Verify file is not corrupted",
                "Try a different media file",
            ],
        )

    try:
        data: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MediaError(
            "Failed to parse ffprobe JSON output",
            context={
                "file_path": str(file_path),
                "error": str(e),
                "stdout_preview": result.stdout[:500] if result.stdout else None,
            },
            suggestions=[
                "Verify ffprobe installation",
                "Check for ffprobe version compatibility",
                "The stdout_preview field shows the first 500 chars of output that failed to parse",
            ],
            cause=e,
        ) from e

    # Extract format information
    format_info: dict[str, Any] = data.get("format", {})
    streams: list[dict[str, Any]] = data.get("streams", [])

    # Get duration
    duration: float
    if "duration" in format_info:
        duration = float(format_info["duration"])
    else:
        # Calculate from streams if not in format
        durations = []
        for stream in streams:
            if "duration" in stream:
                durations.append(float(stream["duration"]))
        if durations:
            duration = max(durations)
        else:
            raise MediaError(
                "Could not determine media duration",
                context={"file_path": str(file_path)},
                suggestions=[
                    "Verify file is a valid media file",
                    "Check file is not corrupted",
                ],
            )

    # Get format name
    format_name: str = format_info.get("format_name", "unknown")

    # Find audio stream for codec, sample_rate, channels
    codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None

    for stream in streams:
        if stream.get("codec_type") == "audio":
            codec = stream.get("codec_name")
            if "sample_rate" in stream:
                with contextlib.suppress(ValueError, TypeError):
                    sample_rate = int(stream["sample_rate"])
            if "channels" in stream:
                with contextlib.suppress(ValueError, TypeError):
                    channels = int(stream["channels"])
            break

    return MediaInfo(
        duration=duration,
        format=format_name,
        codec=codec,
        sample_rate=sample_rate,
        channels=channels,
    )
