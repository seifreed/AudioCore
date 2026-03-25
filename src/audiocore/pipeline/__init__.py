"""Pipeline orchestration module for AudioCore.

This module provides the main transcription pipeline that coordinates:
1. Media format validation and probing
2. Audio extraction to normalized WAV
3. Voice Activity Detection (VAD) for segmentation
4. Backend selection (auto or manual)
5. Transcription execution
6. Result assembly and formatting

The Pipeline class is the main entry point for end-to-end transcription.

Progress callbacks allow monitoring pipeline execution at each stage:

    >>> def on_progress(stage, progress, message):
    ...     print(f"[{stage.value}] {progress:.0%}: {message}")
    >>> result = pipeline.transcribe("audio.mp3", progress_callback=on_progress)

Cancellation tokens enable clean termination mid-pipeline:

    >>> token = CancellationToken()
    >>> # In another thread:
    >>> token.cancel()
    >>> # Pipeline will raise CancelledError when checked
"""

from audiocore.pipeline.cancellation import CancellationToken, CancelledError
from audiocore.pipeline.orchestrator import Pipeline, transcribe
from audiocore.pipeline.progress import PipelineStage, ProgressCallback, ProgressEvent

__all__ = [
    # Main exports
    "Pipeline",
    "transcribe",
    # Progress types
    "PipelineStage",
    "ProgressCallback",
    "ProgressEvent",
    # Cancellation types
    "CancellationToken",
    "CancelledError",
]
