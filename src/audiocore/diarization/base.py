"""Speaker diarization interface and speaker-assignment logic.

Diarization answers "who spoke when": a :class:`Diarizer` turns an audio file
into a list of :class:`SpeakerTurn` spans, and :func:`assign_speakers` labels
transcription segments by matching each to the speaker turn it overlaps most.
The protocol keeps the pipeline independent of any concrete diarizer (the
optional pyannote implementation, or a user's own).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from audiocore.models import Segment

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class SpeakerTurn:
    """A contiguous span attributed to a single speaker.

    Attributes:
        start_time: Start of the turn in seconds.
        end_time: End of the turn in seconds (>= start_time).
        speaker: Speaker label (e.g. ``"SPEAKER_00"``).
    """

    start_time: float
    end_time: float
    speaker: str


@runtime_checkable
class Diarizer(Protocol):
    """Structural interface for a speaker-diarization backend."""

    def diarize(self, audio_path: Path | str) -> list[SpeakerTurn]:
        """Return speaker turns for the given audio file."""
        ...


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> list[Segment]:
    """Return copies of ``segments`` labeled with their dominant speaker.

    Each segment is matched to the speaker turn with which it shares the most
    time; ties resolve to the earliest turn. A segment that overlaps no turn
    keeps ``speaker=None``. Input segments are not mutated.

    Args:
        segments: Transcription segments to label.
        turns: Speaker turns from a diarizer (any order).

    Returns:
        New segments with ``speaker`` populated where a turn overlaps.
    """
    if not turns:
        return list(segments)
    return [_with_speaker(segment, _dominant_speaker(segment, turns)) for segment in segments]


def _dominant_speaker(segment: Segment, turns: list[SpeakerTurn]) -> str | None:
    """Return the speaker whose turn overlaps the segment most, or None."""
    best_speaker: str | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = min(segment.end_time, turn.end_time) - max(segment.start_time, turn.start_time)
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = turn.speaker
    return best_speaker


def _with_speaker(segment: Segment, speaker: str | None) -> Segment:
    """Return a copy of ``segment`` with its speaker label set."""
    if speaker is None:
        return segment.model_copy()
    return segment.model_copy(update={"speaker": speaker})
