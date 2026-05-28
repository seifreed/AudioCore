"""Audio chunking and upload preparation for the OpenAI Whisper backend.

OpenAI's transcription endpoint caps upload size, so oversized inputs are
split into container-compatible chunks with ffmpeg. These are infrastructure
helpers that shell out to ffmpeg/ffprobe; they hold no client state and take
all configuration explicitly.
"""

from __future__ import annotations

import contextlib
import logging
import subprocess
import tempfile
from pathlib import Path

from audiocore.backends.openai_response import parse_positive_duration
from audiocore.errors import TranscriptionError

logger = logging.getLogger(__name__)

# Fraction below the size-derived estimate to retry with, leaving headroom.
CHUNK_SIZE_RETRY_MARGIN = 0.9
# Maximum times to shrink chunk duration before giving up on the upload limit.
MAX_CHUNK_SIZE_ATTEMPTS = 5
_FFMPEG_SEGMENT_TIMEOUT_SECONDS = 3600
_FFPROBE_DURATION_TIMEOUT_SECONDS = 30
_STDERR_CONTEXT_LIMIT = 1000


def split_audio_for_upload(
    audio_path: Path,
    *,
    ffmpeg_path: str,
    ffprobe_path: str,
    max_upload_bytes: int,
    chunk_target_bytes: int,
    chunk_min_duration_seconds: float,
) -> list[Path]:
    """Create temporary chunks that fit below the configured upload limit.

    Raises:
        TranscriptionError: If duration is unknown, ffmpeg produces no chunks,
            or chunks cannot be shrunk below the upload limit.
    """
    duration = get_audio_duration(audio_path, ffprobe_path=ffprobe_path)
    if duration <= 0:
        raise TranscriptionError(
            "Cannot split audio with unknown duration",
            context={"backend": "openai", "file_path": str(audio_path)},
            suggestions=[
                "Verify ffprobe can read the audio file",
                "Try a different audio format",
            ],
        )

    chunk_duration = estimate_chunk_duration(
        audio_path,
        duration,
        chunk_target_bytes=chunk_target_bytes,
        chunk_min_duration_seconds=chunk_min_duration_seconds,
    )
    temp_dir = Path(tempfile.mkdtemp(prefix="audiocore_openai_chunks_"))

    for _attempt in range(MAX_CHUNK_SIZE_ATTEMPTS):
        run_ffmpeg_segment(audio_path, temp_dir, chunk_duration, ffmpeg_path=ffmpeg_path)
        chunks = sorted(temp_dir.glob("chunk_*.*"))
        if not chunks:
            cleanup_chunk_dir(temp_dir)
            raise TranscriptionError(
                "ffmpeg did not create any audio chunks",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Verify ffmpeg can read the audio file",
                    "Try a different audio format",
                ],
            )

        largest_chunk_size = max(chunk.stat().st_size for chunk in chunks)
        if largest_chunk_size <= max_upload_bytes:
            return chunks

        cleanup_chunk_files(temp_dir)
        reduction_ratio = chunk_target_bytes / largest_chunk_size
        next_duration = chunk_duration * reduction_ratio * CHUNK_SIZE_RETRY_MARGIN
        if next_duration < chunk_min_duration_seconds:
            cleanup_chunk_dir(temp_dir)
            raise TranscriptionError(
                "Unable to split audio into chunks below OpenAI upload limit",
                context={
                    "backend": "openai",
                    "file_path": str(audio_path),
                    "largest_chunk_size": largest_chunk_size,
                    "max_upload_size": max_upload_bytes,
                },
                suggestions=[
                    "Use a more compressed audio format",
                    "Increase openai.max_upload_size_mb if your provider supports it",
                ],
            )
        chunk_duration = next_duration

    cleanup_chunk_dir(temp_dir)
    raise TranscriptionError(
        "Unable to produce OpenAI-sized chunks after retries",
        context={"backend": "openai", "file_path": str(audio_path)},
        suggestions=[
            "Use a more compressed audio format",
            "Try reducing openai.chunk_target_size_mb",
        ],
    )


def estimate_chunk_duration(
    audio_path: Path,
    duration: float,
    *,
    chunk_target_bytes: int,
    chunk_min_duration_seconds: float,
) -> float:
    """Estimate chunk duration from observed file bitrate and target size."""
    file_size = audio_path.stat().st_size
    seconds_for_target_size = duration * (chunk_target_bytes / file_size)
    return max(chunk_min_duration_seconds, seconds_for_target_size)


def run_ffmpeg_segment(
    audio_path: Path,
    output_dir: Path,
    chunk_duration: float,
    *,
    ffmpeg_path: str,
) -> None:
    """Split audio with ffmpeg into same-container chunks.

    Raises:
        TranscriptionError: If ffmpeg is missing or fails to segment the file.
    """
    cleanup_chunk_files(output_dir)
    suffix = audio_path.suffix or ".wav"
    output_pattern = output_dir / f"chunk_%04d{suffix}"
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "segment",
        "-segment_time",
        f"{chunk_duration:.6f}",
        "-reset_timestamps",
        "1",
        "-c",
        "copy",
        str(output_pattern),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=_FFMPEG_SEGMENT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as e:
        cleanup_chunk_dir(output_dir)
        raise TranscriptionError(
            f"ffmpeg executable not found: {ffmpeg_path}",
            context={"backend": "openai", "ffmpeg_path": ffmpeg_path},
            suggestions=[
                "Install ffmpeg",
                "Set AppConfig.ffmpeg_path to the ffmpeg executable",
            ],
            cause=e,
        ) from e
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        cleanup_chunk_dir(output_dir)
        stderr = getattr(e, "stderr", None)
        raise TranscriptionError(
            "Failed to split oversized audio for OpenAI transcription",
            context={
                "backend": "openai",
                "file_path": str(audio_path),
                "stderr": str(stderr)[:_STDERR_CONTEXT_LIMIT] if stderr else None,
            },
            suggestions=[
                "Verify the audio file is valid",
                "Verify ffmpeg supports this format",
            ],
            cause=e,
        ) from e


def get_audio_duration(audio_path: Path, *, ffprobe_path: str) -> float:
    """Read audio duration in seconds with ffprobe.

    Raises:
        TranscriptionError: If ffprobe is missing, fails, or returns a
            non-positive or non-finite duration.
    """
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=_FFPROBE_DURATION_TIMEOUT_SECONDS,
        )
        duration = parse_positive_duration(result.stdout.strip())
        if duration is None:
            raise ValueError("ffprobe returned a non-positive or non-finite duration")
        return duration
    except (
        FileNotFoundError,
        ValueError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as e:
        raise TranscriptionError(
            "Failed to read audio duration before OpenAI chunking",
            context={
                "backend": "openai",
                "file_path": str(audio_path),
                "ffprobe_path": ffprobe_path,
            },
            suggestions=[
                "Verify ffprobe is installed",
                "Set AppConfig.ffprobe_path to the ffprobe executable",
                "Verify the audio file is valid",
            ],
            cause=e,
        ) from e


def cleanup_chunk_files(output_dir: Path) -> None:
    """Remove generated chunk files, leaving the directory in place."""
    for chunk_path in output_dir.glob("chunk_*.*"):
        chunk_path.unlink(missing_ok=True)


def cleanup_chunk_dir(output_dir: Path) -> None:
    """Remove generated chunk files and the (now empty) chunk directory."""
    cleanup_chunk_files(output_dir)
    with contextlib.suppress(OSError):
        output_dir.rmdir()
