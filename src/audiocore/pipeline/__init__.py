"""Pipeline orchestration module for AudioCore.

This module provides the main transcription pipeline that coordinates:
1. Media format validation and probing
2. Audio extraction to normalized WAV
3. Voice Activity Detection (VAD) for segmentation
4. Backend selection (auto or manual)
5. Transcription execution
6. Result assembly and formatting

The Pipeline class is the main entry point for end-to-end transcription.
"""

from audiocore.pipeline.orchestrator import Pipeline, transcribe

__all__ = [
    "Pipeline",
    "transcribe",
]
