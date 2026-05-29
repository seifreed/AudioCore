"""Energy-based utterance segmentation for real-time transcription.

A live audio stream arrives as a sequence of small PCM chunks. This module
groups those chunks into *utterances* — runs of speech bounded by silence — so
each completed utterance can be handed to a transcription backend as soon as the
speaker pauses, rather than waiting for the whole stream to end.

Segmentation uses a lightweight root-mean-square energy gate rather than a
neural VAD: it has no heavy dependencies, is deterministic, and is well suited
to the low-latency, chunk-at-a-time nature of real-time capture. The neural
Silero VAD remains the segmenter for offline file transcription.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

# Real-time audio is normalized 16 kHz mono float32, matching the rate the
# transcription backends and Silero expect.
REALTIME_SAMPLE_RATE = 16000
# Default RMS amplitude above which a chunk counts as speech (range [-1, 1]).
DEFAULT_ENERGY_THRESHOLD = 0.015
# Trailing silence that closes an utterance.
DEFAULT_MIN_SILENCE_SECONDS = 0.8
# Utterances shorter than this are treated as noise and dropped.
DEFAULT_MIN_UTTERANCE_SECONDS = 0.3
# Hard cap so a continuous talker is still flushed periodically.
DEFAULT_MAX_UTTERANCE_SECONDS = 30.0


@dataclass(frozen=True)
class Utterance:
    """A completed run of speech ready for transcription.

    Attributes:
        audio: Mono float32 samples for the utterance (including the trailing
            silence that closed it).
        start_time: Offset of the utterance start within the overall stream,
            in seconds, used to place transcribed segments on the timeline.
        sample_rate: Sample rate of ``audio`` in Hz.
    """

    audio: NDArray[np.float32]
    start_time: float
    sample_rate: int = REALTIME_SAMPLE_RATE

    @property
    def duration(self) -> float:
        """Utterance duration in seconds."""
        return len(self.audio) / self.sample_rate


@dataclass
class UtteranceSegmenter:
    """Group streamed audio chunks into utterances using an RMS energy gate.

    Feed each incoming chunk to :meth:`process`; it returns any utterances that
    completed on that chunk. Call :meth:`flush` once the stream ends to emit a
    final in-progress utterance.

    Attributes:
        sample_rate: Expected sample rate of incoming chunks (Hz).
        energy_threshold: RMS amplitude above which a chunk is speech.
        min_silence_seconds: Trailing silence required to close an utterance.
        min_utterance_seconds: Minimum duration for an utterance to be emitted.
        max_utterance_seconds: Maximum duration before a forced flush.
    """

    sample_rate: int = REALTIME_SAMPLE_RATE
    energy_threshold: float = DEFAULT_ENERGY_THRESHOLD
    min_silence_seconds: float = DEFAULT_MIN_SILENCE_SECONDS
    min_utterance_seconds: float = DEFAULT_MIN_UTTERANCE_SECONDS
    max_utterance_seconds: float = DEFAULT_MAX_UTTERANCE_SECONDS

    _consumed_samples: int = field(default=0, init=False)
    _capturing: bool = field(default=False, init=False)
    _start_sample: int = field(default=0, init=False)
    _silence_seconds: float = field(default=0.0, init=False)
    _buffer: list[NDArray[np.float32]] = field(default_factory=list, init=False)

    def process(self, chunk: NDArray[np.floating]) -> list[Utterance]:
        """Consume one audio chunk and return any utterances it completed.

        Args:
            chunk: Mono samples for this step (any float dtype; cast to float32).

        Returns:
            Zero or more utterances that ended on this chunk (usually zero or
            one; a chunk can close one utterance and a long talker may also hit
            the max-duration cap).
        """
        samples = np.asarray(chunk, dtype=np.float32).reshape(-1)
        chunk_start = self._consumed_samples
        self._consumed_samples += len(samples)

        if len(samples) == 0:
            return []

        emitted: list[Utterance] = []
        if self._is_speech(samples):
            if not self._capturing:
                self._capturing = True
                self._start_sample = chunk_start
                self._buffer = []
            self._buffer.append(samples)
            self._silence_seconds = 0.0
        elif self._capturing:
            self._buffer.append(samples)
            self._silence_seconds += len(samples) / self.sample_rate
            if self._silence_seconds >= self.min_silence_seconds:
                utterance = self._finalize()
                if utterance is not None:
                    emitted.append(utterance)

        if self._capturing and self._buffered_seconds() >= self.max_utterance_seconds:
            utterance = self._finalize()
            if utterance is not None:
                emitted.append(utterance)

        return emitted

    def flush(self) -> Utterance | None:
        """Emit any in-progress utterance at the end of the stream."""
        if not self._capturing:
            return None
        return self._finalize()

    def _is_speech(self, samples: NDArray[np.float32]) -> bool:
        """Return True when the chunk's RMS energy exceeds the threshold."""
        rms = math.sqrt(float(np.mean(np.square(samples))))
        return rms >= self.energy_threshold

    def _buffered_seconds(self) -> float:
        """Seconds of audio currently buffered for the open utterance."""
        return sum(len(part) for part in self._buffer) / self.sample_rate

    def _finalize(self) -> Utterance | None:
        """Close the open utterance, resetting state; drop it if too short."""
        audio = np.concatenate(self._buffer) if self._buffer else np.empty(0, dtype=np.float32)
        start_time = self._start_sample / self.sample_rate
        self._capturing = False
        self._buffer = []
        self._silence_seconds = 0.0
        if len(audio) / self.sample_rate < self.min_utterance_seconds:
            return None
        return Utterance(audio=audio, start_time=start_time, sample_rate=self.sample_rate)
