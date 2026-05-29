"""Parallel processing module for AudioCore.

This module provides concurrent processing capabilities for:
- Segment-level parallel transcription
- File-level batch processing

The module enables efficient utilization of system resources when
processing multiple audio files or segments concurrently.

Example:
    >>> from audiocore.parallel import transcribe_files_concurrent
    >>> from pathlib import Path
    >>> from audiocore.models import TranscriptionOptions
    >>>
    >>> # Concurrent file processing
    >>> files = [Path("audio1.mp3"), Path("audio2.mp3")]
    >>> results = await transcribe_files_concurrent(
    ...     files=files,
    ...     options=TranscriptionOptions(),
    ...     max_workers=4
    ... )
"""

from audiocore.parallel.files import FileResult, transcribe_files_concurrent
from audiocore.parallel.segments import transcribe_segments_parallel

__all__ = [
    "transcribe_files_concurrent",
    "FileResult",
    "transcribe_segments_parallel",
]
