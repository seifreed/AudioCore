"""Audio extraction utilities using ffmpeg.

This module provides functions to extract and convert audio from media files
using ffmpeg subprocess calls.
"""

import logging
import re
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from audiocore.errors import InvalidInputError, MediaError
from audiocore.media.probe import probe

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


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
    # Check for shell metacharacters that could enable injection
    dangerous_chars = {"|", "&", ";", "$", "`", "(", ")", "<", ">", "\n", "\r"}
    if any(char in executable_path for char in dangerous_chars):
        raise MediaError(
            "Invalid executable path: contains forbidden characters",
            context={"path": executable_path},
            suggestions=[
                "Use simple executable name (e.g., 'ffmpeg')",
                "Use absolute path without special characters",
            ],
        )

    # Validate existence
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


def _build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    start_time: float | None = None,
    duration: float | None = None,
    ffmpeg_path: str = "ffmpeg",
) -> list[str]:
    """Build ffmpeg command for audio extraction.

    Args:
        input_path: Path to input media file.
        output_path: Path to output WAV file.
        start_time: Optional start time in seconds for seeking.
        duration: Optional duration limit in seconds.
        ffmpeg_path: Path to ffmpeg executable.

    Returns:
        List of command arguments for subprocess.
    """
    command = [ffmpeg_path, "-y"]  # -y to overwrite output

    # Place -ss before -i for fast seeking
    if start_time is not None:
        command.extend(["-ss", str(start_time)])

    command.extend(["-i", str(input_path)])

    if duration is not None:
        command.extend(["-t", str(duration)])

    # Normalize to 16kHz mono PCM WAV
    command.extend(
        [
            "-ar",
            "16000",  # 16kHz sample rate for transcription
            "-ac",
            "1",  # Mono channel
            "-c:a",
            "pcm_s16le",  # Lossless PCM codec
            str(output_path),
        ]
    )

    return command


def _validate_output(output_path: Path) -> None:
    """Validate that output file exists and has content.

    Args:
        output_path: Path to output file to validate.

    Raises:
        MediaError: If output file is missing or empty.
    """
    if not output_path.exists():
        raise MediaError(
            f"Output file not created: {output_path}",
            context={"output_path": str(output_path)},
            suggestions=[
                "Check ffmpeg installation",
                "Verify input file is valid media",
                "Check disk space",
            ],
        )

    if output_path.stat().st_size == 0:
        raise MediaError(
            f"Output file is empty: {output_path}",
            context={"output_path": str(output_path)},
            suggestions=[
                "Verify input file has audio content",
                "Check start_time and duration parameters",
                "Try different input format",
            ],
        )


def _parse_progress(stderr_line: str, total_duration: float) -> float | None:
    """Parse ffmpeg stderr for progress percentage.

    Args:
        stderr_line: Line from ffmpeg stderr output.
        total_duration: Total duration of the media in seconds.

    Returns:
        Progress percentage (0-100) if time found, None otherwise.

    Note:
        Ffmpeg outputs progress as "time=XX:XX:XX.XX" in stderr.
    """
    # Match time= format from ffmpeg stderr
    # Examples: time=00:00:01.23, time=1.23
    time_match = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", stderr_line)
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = float(time_match.group(3))
        current_time = hours * 3600 + minutes * 60 + seconds
        if total_duration > 0:
            return min(100.0, (current_time / total_duration) * 100)

    # Also match decimal time format: time=123.45
    time_match_decimal = re.search(r"time=(\d+\.?\d*)", stderr_line)
    if time_match_decimal:
        current_time = float(time_match_decimal.group(1))
        if total_duration > 0:
            return min(100.0, (current_time / total_duration) * 100)

    return None


def extract_audio(
    input_path: Path | str,
    output_path: Path | None = None,
    start_time: float | None = None,
    duration: float | None = None,
    ffmpeg_path: str = "ffmpeg",
    timeout: float = 3600.0,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Extract audio from media file to normalized WAV format.

    Converts any media file to 16kHz mono WAV format suitable for transcription.
    Supports seeking to a start position and limiting duration.

    Args:
        input_path: Path to input media file.
        output_path: Optional path for output WAV file. If None, creates temp file.
        start_time: Optional start time in seconds for seeking.
        duration: Optional duration limit in seconds.
        ffmpeg_path: Path to ffmpeg executable. Defaults to "ffmpeg".
        timeout: Timeout in seconds for ffmpeg command. Defaults to 3600 (1 hour).
        progress_callback: Optional callback for progress updates (0-100 percentage).

    Returns:
        Path to the extracted audio file (WAV format, 16kHz, mono).

    Raises:
        InvalidInputError: If input file does not exist.
        MediaError: If ffmpeg fails, times out, or output is invalid.

    Example:
        >>> from pathlib import Path
        >>> output = extract_audio(Path("video.mp4"))
        >>> output.suffix
        '.wav'

        >>> # With progress callback
        >>> def on_progress(pct: float):
        ...     print(f"Progress: {pct:.1f}%")
        >>> output = extract_audio(Path("video.mp4"), progress_callback=on_progress)
    """
    input_path = Path(input_path)

    # Validate input file exists
    if not input_path.exists():
        raise InvalidInputError(
            f"Input file not found: {input_path}",
            context={"input_path": str(input_path)},
            suggestions=[
                "Verify the file path is correct",
                "Check file permissions",
                "Ensure the file exists",
            ],
        )

    # Validate ffmpeg executable path (security: prevent command injection)
    _validate_executable_path(ffmpeg_path)

    # Get total duration for progress callback if needed
    total_duration: float | None = None
    if progress_callback is not None:
        try:
            media_info = probe(
                input_path, ffprobe_path=ffmpeg_path.replace("ffmpeg", "ffprobe")
            )
            total_duration = media_info.duration
        except Exception as probe_error:
            # If probe fails, progress callback won't work but extraction can continue
            # Log the error for debugging but don't fail the extraction
            logger.debug(f"Could not probe media for progress: {probe_error}")

    # Create temp file if no output path specified
    created_temp = False
    if output_path is None:
        temp_file = NamedTemporaryFile(
            suffix=".wav", delete=False
        )  # noqa: SIM115 - File must persist for processing
        output_path = Path(temp_file.name)
        temp_file.close()
        created_temp = True

    # Build and run ffmpeg command
    command = _build_ffmpeg_command(
        input_path=input_path,
        output_path=output_path,
        start_time=start_time,
        duration=duration,
        ffmpeg_path=ffmpeg_path,
    )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise MediaError(
            f"ffmpeg executable not found at: {ffmpeg_path}",
            context={"ffmpeg_path": ffmpeg_path, "input_path": str(input_path)},
            suggestions=[
                "Install ffmpeg using your package manager",
                f"Verify {ffmpeg_path} is in PATH or provide full path",
                "Set AUDIOCORE_FFMPEG_PATH environment variable",
            ],
            cause=e,
        ) from e
    except subprocess.TimeoutExpired as e:
        # Ensure process is terminated on timeout
        if e.proc is not None:
            import contextlib

            with contextlib.suppress(Exception):
                e.proc.terminate()
                try:
                    e.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if terminate doesn't work
                    e.proc.kill()
                    e.proc.wait()
        # Clean up temp file if created
        if created_temp and output_path.exists():
            output_path.unlink(missing_ok=True)
        raise MediaError(
            f"ffmpeg timed out after {timeout} seconds",
            context={"timeout": timeout, "input_path": str(input_path)},
            suggestions=[
                f"Try increasing timeout (current: {timeout}s)",
                "Check if file is very large",
                "Verify ffmpeg is responsive",
            ],
            cause=e,
        ) from e

    if result.returncode != 0:
        # Clean up temp file if created
        if created_temp and output_path.exists():
            output_path.unlink(missing_ok=True)
        raise MediaError(
            f"ffmpeg failed with return code {result.returncode}",
            context={
                "return_code": result.returncode,
                "stderr": result.stderr[:1000] if result.stderr else None,
                "input_path": str(input_path),
            },
            suggestions=[
                "Check input file format is supported",
                "Verify input file is not corrupted",
                "Check ffmpeg error message for details",
            ],
        )

    # Parse progress from stderr if callback provided
    if (
        progress_callback is not None
        and total_duration is not None
        and total_duration > 0
    ):
        for line in result.stderr.splitlines():
            progress = _parse_progress(line, total_duration)
            if progress is not None:
                progress_callback(progress)

    # Validate output
    try:
        _validate_output(output_path)
    except MediaError:
        # Clean up temp file if created
        if created_temp and output_path.exists():
            output_path.unlink(missing_ok=True)
        raise

    return output_path


@contextmanager
def temp_audio_file(suffix: str = ".wav"):
    """Create temporary audio file with automatic cleanup.

    Context manager that creates a temporary file path and ensures
    cleanup after use, even if an exception occurs.

    Args:
        suffix: File suffix for the temporary file. Defaults to ".wav".

    Yields:
        Path to the temporary file (file is not created until written to).

    Example:
        >>> with temp_audio_file() as temp_path:
        ...     extract_audio(input_path, temp_path)
        ...     # Process temp_path
        ... # File automatically deleted after context
    """
    temp = NamedTemporaryFile(
        suffix=suffix, delete=False
    )  # noqa: SIM115 - Must persist for caller usage
    temp_path = Path(temp.name)
    temp.close()
    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)
