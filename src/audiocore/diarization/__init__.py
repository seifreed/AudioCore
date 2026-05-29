"""Speaker diarization: assign speaker labels to transcription segments.

Public surface:
    - Diarizer: structural protocol for a diarization backend.
    - SpeakerTurn: a speaker-attributed time span.
    - assign_speakers: label segments by overlap with speaker turns.
    - PyannoteDiarizer: optional pyannote.audio-backed implementation.
"""

from audiocore.diarization.base import Diarizer, SpeakerTurn, assign_speakers
from audiocore.diarization.pyannote_diarizer import PyannoteDiarizer

__all__ = [
    "Diarizer",
    "PyannoteDiarizer",
    "SpeakerTurn",
    "assign_speakers",
]
