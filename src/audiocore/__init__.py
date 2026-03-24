"""
AudioCore - Audio/Video transcription engine with dual backend support.

AudioCore bridges cloud and local transcription with automatic backend
selection, handling audio extraction, VAD segmentation, and output
formatting so developers don't have to.
"""

__version__ = "1.0.0"

# Import commonly used exceptions for convenience
from audiocore.errors import AudioCoreError

__all__ = ["__version__", "AudioCoreError"]
