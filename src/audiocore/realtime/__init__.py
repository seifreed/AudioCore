"""Real-time transcription of live audio streams.

Public surface:
    - AudioSource: structural protocol for a live chunk source.
    - MicrophoneSource: optional ``sounddevice``-backed input capture.
    - UtteranceSegmenter / Utterance: energy-based utterance segmentation.
    - RealtimeTranscriber: stream a source into transcribed segments.
    - transcribe_realtime: convenience wrapper with backend auto-selection.
"""

from audiocore.realtime.segmenter import (
    REALTIME_SAMPLE_RATE,
    Utterance,
    UtteranceSegmenter,
)
from audiocore.realtime.source import AudioSource, MicrophoneSource
from audiocore.realtime.transcriber import RealtimeTranscriber, transcribe_realtime

__all__ = [
    "REALTIME_SAMPLE_RATE",
    "AudioSource",
    "MicrophoneSource",
    "RealtimeTranscriber",
    "Utterance",
    "UtteranceSegmenter",
    "transcribe_realtime",
]
