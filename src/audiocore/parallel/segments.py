"""Segment-level parallel processing for transcription.

This module provides parallel transcription of audio segments.

NOTE: Current backends (OpenAI, Faster-Whisper) transcribe the
complete audio file and generate their own segments internally.
Segment-level parallel processing is a future feature that will
be enabled when backends support processing arbitrary time ranges.

The module structure is ready for future enhancement when:
1. Backends add support for transcribing arbitrary time ranges
2. VAD segments need to be split across multiple workers
3. Large files benefit from segment-based parallelization

For now, use file-level concurrent processing via
audiocore.parallel.files.transcribe_files_concurrent() instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from audiocore.models import (
        MediaInfo,
        Segment,
        TranscriptionOptions,
        TranscriptionResult,
    )


def transcribe_segments_parallel(
    segments: list[Segment],
    audio_path: Path,
    options: TranscriptionOptions,
    max_workers: int = 4,
    media_info: MediaInfo | None = None,
) -> TranscriptionResult:
    """Transcribe audio segments in parallel.

    NOTE: This is a placeholder for future implementation.
    Current backends transcribe the complete audio file and
    generate their own segments internally.

    Args:
        segments: List of audio segments to transcribe.
        audio_path: Path to the audio file.
        options: Transcription options.
        max_workers: Maximum number of parallel workers.
        media_info: Optional media metadata.

    Returns:
        TranscriptionResult with merged segment results.

    Raises:
        NotImplementedError: Currently not implemented.

    Future Behavior:
        When backends support arbitrary time ranges, this function will:
        1. Split segments across workers based on max_workers
        2. Transcribe each segment concurrently
        3. Merge results maintaining chronological order
        4. Return consolidated TranscriptionResult

        Use file-level parallelism instead:
        ```python
        from audiocore.parallel import transcribe_files_concurrent
        results = await transcribe_files_concurrent(files, options)
        ```
    """
    raise NotImplementedError(
        "Segment-level parallel transcription is not yet implemented. "
        "Current backends transcribe complete audio files internally. "
        "Use file-level concurrent processing via "
        "audiocore.parallel.files.transcribe_files_concurrent() instead."
    )


__all__ = ["transcribe_segments_parallel"]
