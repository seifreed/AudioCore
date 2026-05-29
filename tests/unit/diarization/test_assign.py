"""Unit tests for speaker assignment and the Diarizer protocol (v2.0)."""

from __future__ import annotations

from pathlib import Path

from audiocore.diarization import Diarizer, SpeakerTurn, assign_speakers
from audiocore.models import Segment


class _TwoSpeakerDiarizer:
    """A fixed diarizer alternating two speakers; satisfies the protocol."""

    def diarize(self, audio_path: Path | str) -> list[SpeakerTurn]:
        return [
            SpeakerTurn(0.0, 5.0, "SPEAKER_00"),
            SpeakerTurn(5.0, 10.0, "SPEAKER_01"),
        ]


class TestAssignSpeakers:
    """assign_speakers labels segments by dominant overlap."""

    def test_segment_gets_overlapping_speaker(self) -> None:
        """A segment inside one turn is labeled with that turn's speaker."""
        segments = [Segment(start_time=1.0, end_time=4.0, text="hi")]
        turns = [SpeakerTurn(0.0, 5.0, "SPEAKER_00")]
        labeled = assign_speakers(segments, turns)
        assert labeled[0].speaker == "SPEAKER_00"

    def test_dominant_speaker_wins_on_partial_overlap(self) -> None:
        """A segment spanning two turns takes the speaker it overlaps most."""
        # 1.0-5.0 -> 1s with SPEAKER_00 (4-5), 3s with SPEAKER_01 (5-8... no)
        segments = [Segment(start_time=4.0, end_time=9.0, text="hi")]
        turns = [
            SpeakerTurn(0.0, 5.0, "SPEAKER_00"),  # overlap 4-5 = 1s
            SpeakerTurn(5.0, 10.0, "SPEAKER_01"),  # overlap 5-9 = 4s
        ]
        labeled = assign_speakers(segments, turns)
        assert labeled[0].speaker == "SPEAKER_01"

    def test_no_overlap_leaves_speaker_none(self) -> None:
        """A segment outside every turn keeps speaker=None."""
        segments = [Segment(start_time=20.0, end_time=25.0, text="late")]
        turns = [SpeakerTurn(0.0, 5.0, "SPEAKER_00")]
        labeled = assign_speakers(segments, turns)
        assert labeled[0].speaker is None

    def test_empty_turns_returns_segments_unlabeled(self) -> None:
        """With no turns, segments are returned unchanged (speaker None)."""
        segments = [Segment(start_time=0.0, end_time=1.0, text="hi")]
        labeled = assign_speakers(segments, [])
        assert labeled[0].speaker is None

    def test_does_not_mutate_input_segments(self) -> None:
        """Input segments are not mutated; labeling returns copies."""
        original = Segment(start_time=1.0, end_time=4.0, text="hi")
        assign_speakers([original], [SpeakerTurn(0.0, 5.0, "SPEAKER_00")])
        assert original.speaker is None

    def test_preserves_words_when_labeling(self) -> None:
        """Word-level data survives speaker labeling via model_copy."""
        from audiocore.models import Word

        seg = Segment(
            start_time=1.0,
            end_time=4.0,
            text="hi there",
            words=[Word(word="hi", start_time=1.0, end_time=1.5)],
        )
        labeled = assign_speakers([seg], [SpeakerTurn(0.0, 5.0, "SPEAKER_00")])
        assert labeled[0].speaker == "SPEAKER_00"
        assert labeled[0].words is not None
        assert labeled[0].words[0].word == "hi"


class TestDiarizerProtocol:
    """A custom diarizer satisfies the protocol and integrates with assignment."""

    def test_custom_diarizer_satisfies_protocol(self) -> None:
        """The fixed diarizer is recognized as a Diarizer structurally."""
        assert isinstance(_TwoSpeakerDiarizer(), Diarizer)

    def test_end_to_end_assignment_from_diarizer(self) -> None:
        """Turns from a diarizer label two segments with distinct speakers."""
        diarizer = _TwoSpeakerDiarizer()
        turns = diarizer.diarize("clip.wav")
        segments = [
            Segment(start_time=0.5, end_time=4.0, text="first"),
            Segment(start_time=6.0, end_time=9.0, text="second"),
        ]
        labeled = assign_speakers(segments, turns)
        assert labeled[0].speaker == "SPEAKER_00"
        assert labeled[1].speaker == "SPEAKER_01"
