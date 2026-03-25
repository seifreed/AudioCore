"""Voice Activity Detection (VAD) module.

This module provides VAD functionality for segmenting audio into
speech segments, reducing unnecessary transcription time.
"""

from audiocore.vad.silero import SileroVAD

__all__ = ["SileroVAD"]
