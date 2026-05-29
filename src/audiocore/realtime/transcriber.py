"""Real-time transcription: stream a live audio source into segments.

``RealtimeTranscriber`` consumes an :class:`~audiocore.realtime.source.AudioSource`,
groups the incoming chunks into utterances with an energy-based
:class:`~audiocore.realtime.segmenter.UtteranceSegmenter`, and transcribes each
completed utterance with a backend, yielding the resulting segments placed on
the stream timeline. ``transcribe_realtime`` is a convenience that resolves a
backend from configuration the same way the offline pipeline does.
"""

from __future__ import annotations

import logging
import wave
from typing import TYPE_CHECKING

import numpy as np

from audiocore.media import temp_audio_file
from audiocore.models import Segment, TranscriptionOptions, Word
from audiocore.realtime.segmenter import Utterance, UtteranceSegmenter

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from numpy.typing import NDArray

    from audiocore.backends.base import TranscriptionBackend
    from audiocore.config import AppConfig
    from audiocore.realtime.source import AudioSource

logger = logging.getLogger(__name__)

# int16 full-scale used when writing utterance audio to a temporary WAV.
_INT16_MAX = 32767


class RealtimeTranscriber:
    """Transcribe a live audio stream utterance by utterance.

    Example:
        >>> from audiocore.backends import OpenAIBackend
        >>> transcriber = RealtimeTranscriber(OpenAIBackend())
        >>> # for segment in transcriber.stream(mic_source):
        >>> #     print(segment.text)
    """

    def __init__(
        self,
        backend: TranscriptionBackend,
        options: TranscriptionOptions | None = None,
        segmenter: UtteranceSegmenter | None = None,
    ) -> None:
        """Initialize the real-time transcriber.

        Args:
            backend: Transcription backend used for each completed utterance.
            options: Transcription options applied per utterance. Defaults to
                ``TranscriptionOptions()``.
            segmenter: Optional pre-configured utterance segmenter; a default
                energy-based segmenter is used when omitted.
        """
        self._backend = backend
        self._options = options or TranscriptionOptions()
        self._segmenter = segmenter or UtteranceSegmenter()

    def stream(self, source: AudioSource) -> Iterator[Segment]:
        """Yield transcribed segments from a live audio source.

        Iterates the source, segments it into utterances, and transcribes each
        utterance as it completes; a final partial utterance is flushed when the
        source ends. Segment (and word) timings are shifted onto the overall
        stream timeline.

        Args:
            source: Live audio source yielding mono float32 chunks.

        Yields:
            Segment: Each transcribed segment, in stream order.

        Raises:
            TranscriptionError: If the backend fails on an utterance.
            ProcessingError: If the audio source fails (e.g. microphone).
        """
        for chunk in source:
            for utterance in self._segmenter.process(chunk):
                yield from self._transcribe_utterance(utterance)
        final = self._segmenter.flush()
        if final is not None:
            yield from self._transcribe_utterance(final)

    def _transcribe_utterance(self, utterance: Utterance) -> Iterator[Segment]:
        """Transcribe one utterance and yield its timeline-shifted segments."""
        with temp_audio_file(suffix=".wav") as wav_path:
            _write_wav(wav_path, utterance.audio, utterance.sample_rate)
            result = self._backend.transcribe(wav_path, self._options)
            for segment in result.segments:
                yield _shift_segment(segment, utterance.start_time)


def _write_wav(path: Path, audio: NDArray[np.float32], sample_rate: int) -> None:
    """Write mono float32 [-1, 1] samples to a 16-bit PCM WAV file."""
    clipped = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    pcm = (clipped * _INT16_MAX).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())


def _shift_segment(segment: Segment, offset: float) -> Segment:
    """Return a copy of ``segment`` with its (and its words') times shifted."""
    words: list[Word] | None = None
    if segment.words is not None:
        words = [
            Word(
                word=word.word,
                start_time=word.start_time + offset,
                end_time=word.end_time + offset,
                confidence=word.confidence,
            )
            for word in segment.words
        ]
    return Segment(
        start_time=segment.start_time + offset,
        end_time=segment.end_time + offset,
        text=segment.text,
        confidence=segment.confidence,
        words=words,
    )


def transcribe_realtime(
    source: AudioSource,
    *,
    backend: TranscriptionBackend | None = None,
    config: AppConfig | None = None,
    options: TranscriptionOptions | None = None,
) -> Iterator[Segment]:
    """Transcribe a live audio source, resolving a backend from configuration.

    Args:
        source: Live audio source yielding mono float32 chunks.
        backend: Optional explicit backend; when omitted one is selected from
            ``config`` exactly as the offline pipeline does.
        config: Application configuration used for backend selection and setup.
        options: Per-utterance transcription options.

    Yields:
        Segment: Each transcribed segment, in stream order.
    """
    resolved_backend = backend if backend is not None else _resolve_backend(config, options)
    transcriber = RealtimeTranscriber(resolved_backend, options=options)
    yield from transcriber.stream(source)


def _resolve_backend(
    config: AppConfig | None,
    options: TranscriptionOptions | None,
) -> TranscriptionBackend:
    """Select and instantiate a backend the same way the pipeline does."""
    from audiocore.backends import BackendRegistry, BackendSelector, register_builtin_backends
    from audiocore.config import AppConfig

    register_builtin_backends()
    effective_config = config or AppConfig()
    effective_options = options or TranscriptionOptions()
    selector = BackendSelector(config=effective_config)
    backend_type = selector.select(
        backend=effective_options.backend,
        policy=effective_options.backend_preference,
    )
    return BackendRegistry().get_backend(backend_type, config=effective_config)
