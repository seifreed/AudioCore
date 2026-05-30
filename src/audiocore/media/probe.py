"""Media probing utilities using ffprobe.

This module provides functions to extract metadata from audio/video files
using ffprobe (part of ffmpeg).
"""

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from audiocore.errors import InvalidInputError, MediaError
from audiocore.media.safe_args import as_file_argument
from audiocore.models import MediaInfo

# Max characters of ffprobe stdout/stderr retained in error context.
_OUTPUT_PREVIEW_LIMIT = 500


def _validate_audio_stream(streams: list[dict[str, Any]], file_path: Path) -> None:
    """Validate that at least one audio stream exists in the media file.

    Args:
        streams: List of stream dicts from ffprobe output.
        file_path: Path to the media file (for error context).

    Raises:
        MediaError: If no audio stream is found.
    """
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise MediaError(
            f"No audio stream found in {file_path}",
            context={"file_path": str(file_path), "stream_count": len(streams)},
            suggestions=[
                "Verify the file contains an audio track",
                "Check if the file is video-only or image-only",
                "Try a different media file with audio content",
            ],
        )


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
    if not file_path.is_file():
        raise InvalidInputError(
            f"Path is not a file: {file_path}",
            context={"file_path": str(file_path)},
            suggestions=[
                "Provide a media file path, not a directory",
                "Verify the file path is correct",
            ],
        )


def _parse_duration(value: object) -> float | None:
    """Parse a positive ffprobe duration value, returning None for invalid values."""
    if not isinstance(value, str | int | float):
        return None
    try:
        duration = float(value)
    except ValueError:
        return None
    if not math.isfinite(duration):
        return None
    return duration if duration > 0 else None


def _parse_positive_int(value: object) -> int | None:
    """Parse a positive integer metadata value, returning None for invalid values."""
    if not isinstance(value, str | int | float):
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def probe(
    file_path: Path | str,
    ffprobe_path: str = "ffprobe",
    timeout: float = 30.0,
) -> MediaInfo:
    """Probe a media file for metadata using ffprobe.

    Extracts duration, format, codec, sample rate, and channel information
    from audio/video files.

    Args:
        file_path: Path to the media file to probe.
        ffprobe_path: Path to ffprobe executable. Defaults to "ffprobe".
        timeout: Timeout in seconds for ffprobe command. Defaults to 30.0.

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
    if not math.isfinite(timeout) or timeout <= 0:
        raise InvalidInputError(
            f"Invalid timeout: {timeout}",
            context={"file_path": str(file_path), "timeout": timeout},
            suggestions=["Use a finite timeout greater than 0 seconds"],
        )

    stdout = _run_ffprobe(file_path, ffprobe_path, timeout)
    data = _parse_ffprobe_output(stdout, file_path)
    return _build_media_info(data, file_path)


def _run_ffprobe(file_path: Path, ffprobe_path: str, timeout: float) -> str:
    """Run ffprobe and return its stdout, mapping failures to MediaError."""
    command = [
        ffprobe_path,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        as_file_argument(file_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            text=True,
        )
    except FileNotFoundError as e:
        raise MediaError(
            f"ffprobe not found: {ffprobe_path}",
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
                "stderr": result.stderr[:_OUTPUT_PREVIEW_LIMIT] if result.stderr else None,
                "file_path": str(file_path),
            },
            suggestions=[
                "Check file format is supported",
                "Verify file is not corrupted",
                "Try a different media file",
            ],
        )

    return result.stdout


def _parse_ffprobe_output(stdout: str, file_path: Path) -> dict[str, Any]:
    """Parse ffprobe JSON output, mapping decode errors to MediaError."""
    try:
        data: dict[str, Any] = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise MediaError(
            "Failed to parse ffprobe JSON output",
            context={
                "file_path": str(file_path),
                "error": str(e),
                "stdout_preview": stdout[:_OUTPUT_PREVIEW_LIMIT] if stdout else None,
            },
            suggestions=[
                "Verify ffprobe installation",
                "Check for ffprobe version compatibility",
                "The stdout_preview field shows the first 500 chars of output that failed to parse",
            ],
            cause=e,
        ) from e
    return data


def _resolve_duration(
    format_info: dict[str, Any], streams: list[dict[str, Any]], file_path: Path
) -> float:
    """Resolve duration from format metadata, falling back to the max stream duration."""
    duration = _parse_duration(format_info.get("duration"))
    if duration is not None:
        return duration

    durations = [
        parsed_duration
        for stream in streams
        if (parsed_duration := _parse_duration(stream.get("duration"))) is not None
    ]
    if durations:
        return max(durations)

    raise MediaError(
        "Could not determine media duration",
        context={"file_path": str(file_path)},
        suggestions=[
            "Verify file is a valid media file",
            "Check file is not corrupted",
        ],
    )


def _build_media_info(data: dict[str, Any], file_path: Path) -> MediaInfo:
    """Build MediaInfo from parsed ffprobe data, requiring an audio stream."""
    format_info: dict[str, Any] = data.get("format", {})
    streams: list[dict[str, Any]] = data.get("streams", [])

    duration = _resolve_duration(format_info, streams, file_path)
    format_name: str = format_info.get("format_name", "unknown")

    _validate_audio_stream(streams, file_path)

    stream = next(s for s in streams if s.get("codec_type") == "audio")
    codec: str | None = stream.get("codec_name")
    sample_rate = _parse_positive_int(stream["sample_rate"]) if "sample_rate" in stream else None
    channels = _parse_positive_int(stream["channels"]) if "channels" in stream else None

    return MediaInfo(
        duration=duration,
        format=format_name,
        codec=codec,
        sample_rate=sample_rate,
        channels=channels,
    )
