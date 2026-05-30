"""Unit tests for the energy-based utterance segmenter (real-time, v2.0)."""

from __future__ import annotations

import numpy as np

from audiocore.realtime.segmenter import UtteranceSegmenter

_RATE = 16000
_BLOCK = 480  # 30 ms


def _speech(amplitude: float = 0.1, frames: int = _BLOCK) -> np.ndarray:
    """A loud, constant-amplitude block (RMS well above the gate)."""
    return np.full(frames, amplitude, dtype=np.float32)


def _silence(frames: int = _BLOCK) -> np.ndarray:
    """A silent (zero) block."""
    return np.zeros(frames, dtype=np.float32)


def _fast_segmenter() -> UtteranceSegmenter:
    """A segmenter with short thresholds so tests stay quick."""
    return UtteranceSegmenter(
        sample_rate=_RATE,
        energy_threshold=0.015,
        min_silence_seconds=2 * _BLOCK / _RATE,  # two silent blocks close it
        min_utterance_seconds=_BLOCK / _RATE,  # one speech block is enough
        max_utterance_seconds=1.0,
    )


class TestUtteranceSegmentation:
    """Speech runs bounded by silence are emitted as utterances."""

    def test_speech_then_silence_emits_utterance(self) -> None:
        """A speech run closed by enough silence yields one utterance."""
        seg = _fast_segmenter()
        emitted = []
        for _ in range(3):
            emitted += seg.process(_speech())
        # No utterance until the closing silence arrives.
        assert emitted == []
        emitted += seg.process(_silence())
        assert emitted == []
        emitted += seg.process(_silence())
        assert len(emitted) == 1
        assert emitted[0].duration > 0

    def test_utterance_start_time_tracks_offset(self) -> None:
        """The utterance start_time reflects leading silence before speech."""
        seg = _fast_segmenter()
        seg.process(_silence())
        seg.process(_silence())  # 2 leading silent blocks
        seg.process(_speech())
        seg.process(_silence())
        emitted = seg.process(_silence())
        assert len(emitted) == 1
        expected_start = 2 * _BLOCK / _RATE
        assert abs(emitted[0].start_time - expected_start) < 1e-6

    def test_short_blip_is_dropped(self) -> None:
        """A speech run shorter than min_utterance_seconds is discarded."""
        seg = UtteranceSegmenter(
            sample_rate=_RATE,
            energy_threshold=0.015,
            min_silence_seconds=_BLOCK / _RATE,
            min_utterance_seconds=10 * _BLOCK / _RATE,  # require a long run
            max_utterance_seconds=1.0,
        )
        emitted = seg.process(_speech())
        emitted += seg.process(_silence())
        assert emitted == []

    def test_flush_emits_in_progress_utterance(self) -> None:
        """flush() surfaces a speech run still open at stream end."""
        seg = _fast_segmenter()
        seg.process(_speech())
        seg.process(_speech())
        flushed = seg.flush()
        assert flushed is not None
        assert flushed.start_time == 0.0

    def test_flush_returns_none_when_idle(self) -> None:
        """flush() with no open utterance returns None."""
        seg = _fast_segmenter()
        seg.process(_silence())
        assert seg.flush() is None

    def test_max_duration_forces_split(self) -> None:
        """A continuous talker is force-flushed at the max duration."""
        seg = UtteranceSegmenter(
            sample_rate=_RATE,
            energy_threshold=0.015,
            min_silence_seconds=10.0,
            min_utterance_seconds=_BLOCK / _RATE,
            max_utterance_seconds=3 * _BLOCK / _RATE,  # 3 blocks -> forced flush
        )
        emitted = []
        for _ in range(3):
            emitted += seg.process(_speech())
        assert len(emitted) == 1

    def test_empty_chunk_is_ignored(self) -> None:
        """A zero-length chunk produces nothing and does not crash."""
        seg = _fast_segmenter()
        assert seg.process(np.empty(0, dtype=np.float32)) == []

    def test_max_duration_reached_but_utterance_too_short_emits_nothing(self) -> None:
        """Hitting max duration with sub-min audio drops the forced flush.

        With max_utterance_seconds below min_utterance_seconds, the buffer
        crosses the max bound while still shorter than the minimum, so the
        forced finalize returns None and nothing is emitted.
        """
        seg = UtteranceSegmenter(
            sample_rate=_RATE,
            energy_threshold=0.015,
            min_silence_seconds=10.0,
            min_utterance_seconds=100 * _BLOCK / _RATE,  # unreachably long minimum
            max_utterance_seconds=_BLOCK / _RATE / 2,  # crossed by the first block
        )
        emitted = seg.process(_speech())
        assert emitted == []
        assert seg._capturing is False  # forced finalize reset state
