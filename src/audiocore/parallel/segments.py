"""Segment-level parallel processing for transcription.

This module transcribes individual speech segments concurrently. Each segment's
audio range is extracted to a temporary clip with ffmpeg, transcribed on the
selected backend, and its timings are offset back into the original timeline.
The per-segment transcriptions are merged into a single chronological
``TranscriptionResult``.

Segment-level parallelism overlaps per-segment latency, so it helps most with
the network-bound OpenAI backend. The local faster-whisper backend serializes
inference on its shared model, so concurrency there yields little speedup —
prefer ``audiocore.parallel.files.transcribe_files_concurrent()`` for local
batch workloads.

Concurrency note: this function owns a *scoped* ``ThreadPoolExecutor`` that is
shut down before it returns. It deliberately does not reuse the process-level
executor that ``parallel.files`` / ``async_transcribe`` share for file-level
work — nesting a segment fan-out inside that bounded pool could starve it.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from audiocore.backends import BackendRegistry, BackendSelector, register_builtin_backends
from audiocore.config import AppConfig
from audiocore.errors import InvalidInputError
from audiocore.media import extract_audio, probe, temp_audio_file
from audiocore.models import Segment, TranscriptionResult

if TYPE_CHECKING:
    from audiocore.backends.base import TranscriptionBackend
    from audiocore.models import MediaInfo, TranscriptionOptions

logger = logging.getLogger(__name__)

# Segments shorter than this hold no transcribable audio once extracted.
_MIN_SEGMENT_DURATION_SECONDS = 1e-3


def transcribe_segments_parallel(
    segments: list[Segment],
    audio_path: Path,
    options: TranscriptionOptions,
    max_workers: int = 4,
    media_info: MediaInfo | None = None,
) -> TranscriptionResult:
    """Transcribe audio segments in parallel and merge them chronologically.

    Each segment is extracted to a temporary clip and transcribed on the backend
    selected from ``options`` (honoring ``options.backend`` and
    ``options.backend_preference``). The resulting per-clip segments are shifted
    by the source segment's start time so the merged result keeps the original
    timeline.

    Args:
        segments: Speech segments (e.g. from VAD) to transcribe. Segments with a
            non-positive duration are skipped — they carry no audio.
        audio_path: Path to the source audio file the segments index into.
        options: Transcription options, including the backend selection inputs.
        max_workers: Maximum number of segments transcribed concurrently.
        media_info: Optional media metadata. When omitted, the source file is
            probed to populate the result's ``media_info``.

    Returns:
        TranscriptionResult with all segment transcriptions merged in start-time
        order.

    Raises:
        ValueError: If ``max_workers`` is less than 1.
        InvalidInputError: If ``audio_path`` does not exist or is not a file.
        BackendUnavailableError: If no transcription backend is available.
        MediaError: If a segment's audio cannot be extracted.
        TranscriptionError: If a segment fails to transcribe.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise InvalidInputError(
            f"Audio file not found: {audio_path}",
            context={"file_path": str(audio_path)},
            suggestions=[
                "Verify the file path is correct",
                "Ensure the file exists",
            ],
        )

    register_builtin_backends()
    config = AppConfig()
    backend_type = BackendSelector(config=config).select(
        backend=options.backend,
        policy=options.backend_preference,
    )
    backend = BackendRegistry().get_backend(backend_type, config=config)

    start_time = time.time()
    combined_segments = _transcribe_all_segments(
        segments, audio_path, options, config, backend, max_workers
    )
    processing_time_seconds = time.time() - start_time

    resolved_media_info = media_info or probe(audio_path, ffprobe_path=config.ffprobe_path)

    logger.debug(
        "Segment-level transcription complete for %s: %d input segments, %d output segments",
        audio_path.name,
        len(segments),
        len(combined_segments),
    )

    return TranscriptionResult(
        segments=combined_segments,
        media_info=resolved_media_info,
        config_used=options,
        processing_time_seconds=processing_time_seconds,
        backend_used=backend_type,
    )


def _transcribe_all_segments(
    segments: list[Segment],
    audio_path: Path,
    options: TranscriptionOptions,
    config: AppConfig,
    backend: TranscriptionBackend,
    max_workers: int,
) -> list[Segment]:
    """Transcribe each non-empty segment concurrently and merge by start time."""
    transcribable = [
        segment
        for segment in segments
        if segment.end_time - segment.start_time > _MIN_SEGMENT_DURATION_SECONDS
    ]
    if not transcribable:
        return []

    worker_count = min(max_workers, len(transcribable))
    with ThreadPoolExecutor(
        max_workers=worker_count, thread_name_prefix="audiocore-segment-"
    ) as executor:
        segment_groups = executor.map(
            lambda segment: _transcribe_one_segment(segment, audio_path, options, config, backend),
            transcribable,
        )
        combined = [shifted for group in segment_groups for shifted in group]

    combined.sort(key=lambda segment: (segment.start_time, segment.end_time))
    return combined


def _transcribe_one_segment(
    segment: Segment,
    audio_path: Path,
    options: TranscriptionOptions,
    config: AppConfig,
    backend: TranscriptionBackend,
) -> list[Segment]:
    """Extract one segment's audio, transcribe it, and offset the result timings."""
    duration = segment.end_time - segment.start_time
    with temp_audio_file(suffix=".wav") as clip_path:
        extract_audio(
            audio_path,
            clip_path,
            start_time=segment.start_time,
            duration=duration,
            ffmpeg_path=config.ffmpeg_path,
            ffprobe_path=config.ffprobe_path,
        )
        clip_result = backend.transcribe(clip_path, options)

    return [
        Segment(
            start_time=clip_segment.start_time + segment.start_time,
            end_time=clip_segment.end_time + segment.start_time,
            text=clip_segment.text,
            confidence=clip_segment.confidence,
        )
        for clip_segment in clip_result.segments
    ]


__all__ = ["transcribe_segments_parallel"]
