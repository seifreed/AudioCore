"""Audio extraction utilities using ffmpeg.

This module provides functions to extract and convert audio from media files
using ffmpeg subprocess calls.
"""

from __future__ import annotations

import logging
import math
import re
import subprocess
import time
from collections.abc import Callable
from contextlib import contextmanager, suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from audiocore.errors import InvalidInputError, MediaError
from audiocore.media.probe import probe

logger = logging.getLogger(__name__)

# Seconds to wait for the ffmpeg process to reap after its stderr stream closes.
_PROCESS_WAIT_TIMEOUT_SECONDS = 5.0
# Maximum stderr characters retained in error context to avoid bulky payloads.
_STDERR_CONTEXT_LIMIT = 1000


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
    """Parse ffmpeg stderr for progress fraction.

    Args:
        stderr_line: Line from ffmpeg stderr output.
        total_duration: Total duration of the media in seconds.

    Returns:
        Progress fraction (0.0-1.0) if time found, None otherwise.

    Note:
        Ffmpeg outputs progress as "time=XX:XX:XX.XX" in stderr.
        The return value is a fraction (0.0 to 1.0), matching the
        Pipeline's progress_callback convention.
    """
    # Match time= format from ffmpeg progress lines.
    # Use word boundary / start-of-line context to avoid matching
    # time= inside filenames or metadata.
    # FFmpeg progress lines typically look like: "frame=  120 fps= 30 q=28.0 time=00:00:05.00..."
    # or: "size=    1234kB time=00:00:05.00 bitrate=  ..."
    # Match HH:MM:SS.ms format first (most common)
    time_match = re.search(
        r"(?:^|\s|size=\s*\S+|frame=\s*\S+)time=(\d+):(\d+):(\d+\.?\d*)", stderr_line
    )
    if time_match:
        hours = int(time_match.group(1))
        minutes = int(time_match.group(2))
        seconds = float(time_match.group(3))
        current_time = hours * 3600 + minutes * 60 + seconds
        if total_duration > 0:
            return max(0.0, min(1.0, current_time / total_duration))
        return None

    # Also match decimal time format: time=123.45 (require decimal point to avoid matching HH:MM:SS)
    time_match_decimal = re.search(
        r"(?:^|\s|size=\s*\S+|frame=\s*\S+)time=(\d+\.\d+)(?!\d*:)", stderr_line
    )
    if time_match_decimal:
        current_time = float(time_match_decimal.group(1))
        if total_duration > 0:
            return max(0.0, min(1.0, current_time / total_duration))

    return None


def _validate_extract_inputs(
    input_path: Path,
    timeout: float,
    start_time: float | None,
    duration: float | None,
) -> None:
    """Validate extract_audio arguments, raising InvalidInputError on bad values."""
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
    if not input_path.is_file():
        raise InvalidInputError(
            f"Input path is not a file: {input_path}",
            context={"input_path": str(input_path)},
            suggestions=[
                "Provide a media file path, not a directory",
                "Verify the file path is correct",
            ],
        )
    if not math.isfinite(timeout) or timeout <= 0:
        raise InvalidInputError(
            f"Invalid timeout: {timeout}",
            context={"input_path": str(input_path), "timeout": timeout},
            suggestions=["Use a finite timeout greater than 0 seconds"],
        )
    if start_time is not None and (not math.isfinite(start_time) or start_time < 0):
        raise InvalidInputError(
            f"Invalid start_time: {start_time}",
            context={"input_path": str(input_path), "start_time": start_time},
            suggestions=["Use a finite start_time greater than or equal to 0"],
        )
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise InvalidInputError(
            f"Invalid duration: {duration}",
            context={"input_path": str(input_path), "duration": duration},
            suggestions=["Use a finite duration greater than 0"],
        )


def _probe_total_duration(
    input_path: Path,
    ffmpeg_path: str,
    ffprobe_path: str | None,
) -> float | None:
    """Probe media duration for progress reporting; return None if probing fails.

    Probe failure is non-fatal: extraction proceeds without progress reporting.
    """
    try:
        effective_ffprobe = ffprobe_path
        if effective_ffprobe is None:
            import shutil

            # Try shutil.which first for reliable discovery
            effective_ffprobe = shutil.which("ffprobe")
            if effective_ffprobe is None:
                # Derive from ffmpeg path as fallback
                ffmpeg_path_obj = Path(ffmpeg_path)
                derived = ffmpeg_path_obj.parent / ffmpeg_path_obj.name.replace(
                    "ffmpeg", "ffprobe", 1
                )
                if Path(derived).exists():
                    effective_ffprobe = str(derived)
        media_info = probe(input_path, ffprobe_path=effective_ffprobe)
        return media_info.duration
    except Exception as probe_error:
        logger.debug(f"Could not probe media for progress: {probe_error}")
        return None


def _resolve_output_path(output_path: Path | None) -> tuple[Path, Path | None]:
    """Return (output_path, temp_to_cleanup), creating a temp WAV when none given.

    When a temp file is created the caller owns cleanup; the second element
    is the path to remove on failure (None when the caller supplied a path).
    """
    if output_path is not None:
        return output_path, None
    # SIM115: temp file must persist for processing, cleaned up by caller
    temp_file = NamedTemporaryFile(suffix=".wav", delete=False)  # noqa: SIM115
    resolved = Path(temp_file.name)
    temp_file.close()
    logger.debug(
        "Created temp file for audio extraction: %s. Caller is responsible for cleanup.",
        resolved,
    )
    return resolved, resolved


def _cleanup_temp(temp_file_to_cleanup: Path | None, output_path: Path) -> None:
    """Remove the temp output file if one was created for this extraction."""
    if temp_file_to_cleanup and output_path.exists():
        output_path.unlink(missing_ok=True)


def _run_ffmpeg_streaming(
    command: list[str],
    timeout: float,
    total_duration: float,
    progress_callback: Callable[[float], None],
    input_path: Path,
    ffmpeg_path: str,
) -> tuple[int, str]:
    """Run ffmpeg streaming stderr to emit progress; return (returncode, stderr)."""
    # When streaming stderr, use DEVNULL for stdout to avoid pipe deadlock.
    # ffmpeg writes progress to stderr, not stdout, so we don't need stdout.
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr_lines: list[str] = []
    deadline = time.monotonic() + timeout if timeout > 0 else None
    try:
        if process.stderr is None:
            with suppress(ProcessLookupError):
                process.kill()
            process.wait()
            raise MediaError(
                "ffmpeg stderr pipe was not available for progress tracking",
                context={"input_path": str(input_path), "ffmpeg_path": ffmpeg_path},
                suggestions=[
                    "Retry without a progress callback",
                    "Verify ffmpeg can be started normally",
                ],
            )
        for line in process.stderr:
            if deadline is not None and time.monotonic() > deadline:
                with suppress(ProcessLookupError):
                    process.kill()
                process.wait()
                raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)
            stderr_lines.append(line)
            progress = _parse_progress(line, total_duration)
            if progress is not None:
                progress_callback(progress)
    except subprocess.TimeoutExpired:
        raise
    except BaseException:
        # Ensure process is cleaned up on any exception (e.g., KeyboardInterrupt)
        with suppress(ProcessLookupError):
            process.kill()
        process.wait()
        raise

    returncode = process.wait(timeout=_PROCESS_WAIT_TIMEOUT_SECONDS)
    return returncode, "".join(stderr_lines)


def _run_ffmpeg_buffered(command: list[str], timeout: float) -> tuple[int, str]:
    """Run ffmpeg to completion, buffering output; return (returncode, stderr)."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    communicate_timeout = timeout if timeout > 0 else None
    try:
        _stdout, stderr_data = process.communicate(timeout=communicate_timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise
    returncode = process.returncode if process.returncode is not None else 0
    # Return stderr verbatim so line breaks survive into error context, matching
    # the streaming path (which joins newline-terminated lines).
    return returncode, stderr_data or ""


def _run_ffmpeg(
    command: list[str],
    timeout: float,
    total_duration: float | None,
    progress_callback: Callable[[float], None] | None,
    input_path: Path,
    ffmpeg_path: str,
) -> tuple[int, str]:
    """Run ffmpeg, streaming progress when a callback and duration are available."""
    if progress_callback is not None and total_duration is not None and total_duration > 0:
        return _run_ffmpeg_streaming(
            command, timeout, total_duration, progress_callback, input_path, ffmpeg_path
        )
    return _run_ffmpeg_buffered(command, timeout)


def extract_audio(
    input_path: Path | str,
    output_path: Path | str | None = None,
    start_time: float | None = None,
    duration: float | None = None,
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str | None = None,
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
        progress_callback: Optional callback for progress updates (0.0-1.0 fraction).

    Returns:
        Path to the extracted audio file (WAV format, 16kHz, mono).
        When output_path is None, the caller is responsible for cleaning
        up the returned temporary file. Use temp_audio_file() context
        manager for automatic cleanup.

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
    resolved_output = Path(output_path) if output_path is not None else None

    _validate_extract_inputs(input_path, timeout, start_time, duration)

    total_duration: float | None = None
    if progress_callback is not None:
        total_duration = _probe_total_duration(input_path, ffmpeg_path, ffprobe_path)

    out_path, temp_file_to_cleanup = _resolve_output_path(resolved_output)

    command = _build_ffmpeg_command(
        input_path=input_path,
        output_path=out_path,
        start_time=start_time,
        duration=duration,
        ffmpeg_path=ffmpeg_path,
    )

    try:
        returncode, stderr = _run_ffmpeg(
            command, timeout, total_duration, progress_callback, input_path, ffmpeg_path
        )
    except FileNotFoundError as e:
        _cleanup_temp(temp_file_to_cleanup, out_path)
        raise MediaError(
            f"ffmpeg executable not found: {ffmpeg_path}",
            context={"ffmpeg_path": ffmpeg_path, "input_path": str(input_path)},
            suggestions=[
                "Install ffmpeg using your package manager",
                f"Verify {ffmpeg_path} is in PATH or provide full path",
                "Set AUDIOCORE_FFMPEG_PATH environment variable",
            ],
            cause=e,
        ) from e
    except subprocess.TimeoutExpired as e:
        _cleanup_temp(temp_file_to_cleanup, out_path)
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
    except BaseException:
        # Clean up temp file on any unexpected exception (e.g., KeyboardInterrupt)
        _cleanup_temp(temp_file_to_cleanup, out_path)
        raise

    if returncode != 0:
        _cleanup_temp(temp_file_to_cleanup, out_path)
        raise MediaError(
            f"ffmpeg failed with return code {returncode}",
            context={
                "return_code": returncode,
                "stderr": stderr[:_STDERR_CONTEXT_LIMIT] if stderr else None,
                "input_path": str(input_path),
            },
            suggestions=[
                "Check input file format is supported",
                "Verify input file is not corrupted",
                "Check ffmpeg error message for details",
            ],
        )

    try:
        _validate_output(out_path)
    except MediaError:
        _cleanup_temp(temp_file_to_cleanup, out_path)
        raise

    return out_path


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
    # SIM115: temp file must persist for caller usage, deleted in finally block
    temp = NamedTemporaryFile(suffix=suffix, delete=False)  # noqa: SIM115
    temp_path = Path(temp.name)
    temp.close()
    try:
        yield temp_path
    finally:
        temp_path.unlink(missing_ok=True)
