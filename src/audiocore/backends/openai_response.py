"""Response normalization for the OpenAI Whisper backend.

Translates OpenAI verbose_json responses (or dict-compatible payloads from
compatible providers) into AudioCore's TranscriptionResult model. These are
pure functions with no network or client dependency.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

from audiocore.errors import TranscriptionError
from audiocore.models import (
    MIN_MEDIA_DURATION_SECONDS,
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
)
from audiocore.types import BackendType

logger = logging.getLogger(__name__)


def get_response_value(obj: object, key: str) -> object | None:
    """Read an OpenAI response field from SDK objects or dict-compatible data."""
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def parse_positive_duration(value: object) -> float | None:
    """Parse positive finite durations from provider responses or ffprobe output."""
    try:
        duration = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(duration) or duration <= 0:
        return None
    return duration


def parse_transcription_response(
    response: object,
    audio_path: Path,
    options: TranscriptionOptions,
    processing_time_seconds: float,
    *,
    redact: Callable[[str], str],
) -> TranscriptionResult:
    """Parse an OpenAI response into AudioCore's result model.

    Args:
        response: The OpenAI SDK response object or dict-compatible payload.
        audio_path: Source audio path (used for format and error context).
        options: The options used for the request, echoed into the result.
        processing_time_seconds: Wall-clock time spent on the request.
        redact: Callable that strips API keys from error text before raising.

    Raises:
        TranscriptionError: If the response cannot be parsed.
    """
    try:
        segments = _extract_segments(response)
        media_duration = _resolve_media_duration(response, segments)
        segments = _ensure_segments(response, segments, media_duration)

        media_info = MediaInfo(
            duration=media_duration,
            format=audio_path.suffix.lstrip("."),
        )
        result = TranscriptionResult(
            segments=segments,
            media_info=media_info,
            config_used=options,
            processing_time_seconds=processing_time_seconds,
            backend_used=BackendType.OPENAI,
        )

        logger.debug(
            "OpenAI transcription complete for %s: %d segments, %.2fs processing",
            audio_path,
            len(segments),
            processing_time_seconds,
        )
        return result

    except Exception as e:
        raise TranscriptionError(
            f"Failed to parse OpenAI response: {redact(str(e))}",
            context={"backend": "openai", "file_path": str(audio_path)},
            suggestions=[
                "Check API response format",
                "Try with different audio file",
            ],
            cause=e,
        ) from e


def _extract_segments(response: object) -> list[Segment]:
    """Extract timestamped segments from a verbose_json response."""
    segments: list[Segment] = []
    response_segments = get_response_value(response, "segments")
    if response_segments:
        for seg in cast("list[object]", response_segments):
            start = get_response_value(seg, "start")
            end = get_response_value(seg, "end")
            text = get_response_value(seg, "text")
            segments.append(
                Segment(
                    start_time=float(start),  # type: ignore[arg-type]
                    end_time=float(end),  # type: ignore[arg-type]
                    text=text if isinstance(text, str) else str(text or ""),
                )
            )
    return segments


def _resolve_media_duration(response: object, segments: list[Segment]) -> float:
    """Resolve media duration from the response, falling back to segment timing."""
    response_duration = parse_positive_duration(get_response_value(response, "duration"))
    if response_duration is not None:
        return response_duration
    if segments:
        return max(segment.end_time for segment in segments)
    return MIN_MEDIA_DURATION_SECONDS


def _ensure_segments(
    response: object, segments: list[Segment], media_duration: float
) -> list[Segment]:
    """Preserve top-level text as a single segment when no segments were returned.

    Some compatible providers return only top-level text even when verbose_json
    was requested; keep that text instead of an empty transcription.
    """
    if segments:
        return segments
    response_text = get_response_value(response, "text")
    if isinstance(response_text, str) and response_text.strip():
        return [
            Segment(
                start_time=0.0,
                end_time=media_duration,
                text=response_text.strip(),
            )
        ]
    return segments
