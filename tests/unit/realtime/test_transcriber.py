"""Unit tests for RealtimeTranscriber and audio sources (real-time, v2.0)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from audiocore.errors import ProcessingError
from audiocore.models import (
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
)
from audiocore.realtime import (
    AudioSource,
    MicrophoneSource,
    RealtimeTranscriber,
    UtteranceSegmenter,
)
from audiocore.types import BackendType

_RATE = 16000
_BLOCK = 480


class _ListSource:
    """An AudioSource backed by a fixed list of chunks."""

    def __init__(self, chunks: list[np.ndarray], sample_rate: int = _RATE) -> None:
        self.sample_rate = sample_rate
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _RecordingBackend:
    """A backend stub that returns one segment per utterance it transcribes."""

    def __init__(self) -> None:
        self.received_paths: list[Path] = []
        self.path_existed: list[bool] = []

    def transcribe(self, audio_path, options: TranscriptionOptions) -> TranscriptionResult:
        path = Path(audio_path)
        self.received_paths.append(path)
        self.path_existed.append(path.exists())
        return TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=0.5, text="hello")],
            media_info=MediaInfo(duration=0.5, format="wav"),
            config_used=options,
            processing_time_seconds=0.0,
            backend_used=BackendType.FASTER_WHISPER,
        )


def _fast_segmenter() -> UtteranceSegmenter:
    return UtteranceSegmenter(
        sample_rate=_RATE,
        energy_threshold=0.015,
        min_silence_seconds=2 * _BLOCK / _RATE,
        min_utterance_seconds=_BLOCK / _RATE,
        max_utterance_seconds=1.0,
    )


class TestRealtimeTranscriber:
    """Streaming a source produces timeline-shifted segments per utterance."""

    def test_stream_transcribes_each_utterance(self) -> None:
        """Two silence-separated utterances produce two backend calls."""
        speech = np.full(_BLOCK, 0.1, dtype=np.float32)
        silence = np.zeros(_BLOCK, dtype=np.float32)
        # utterance 1: speech, then closing silence; utterance 2: speech; flush.
        chunks = [speech, speech, silence, silence, speech, speech]
        source = _ListSource(chunks)
        backend = _RecordingBackend()
        transcriber = RealtimeTranscriber(backend, segmenter=_fast_segmenter())

        segments = list(transcriber.stream(source))

        assert len(backend.received_paths) == 2
        assert all(backend.path_existed)  # temp WAV present during transcription
        assert len(segments) == 2

    def test_segment_times_are_shifted_onto_stream_timeline(self) -> None:
        """The second utterance's segment is offset by its stream start time."""
        speech = np.full(_BLOCK, 0.1, dtype=np.float32)
        silence = np.zeros(_BLOCK, dtype=np.float32)
        chunks = [speech, silence, silence, speech]
        source = _ListSource(chunks)
        backend = _RecordingBackend()
        transcriber = RealtimeTranscriber(backend, segmenter=_fast_segmenter())

        segments = list(transcriber.stream(source))

        # First utterance starts at t=0; second starts after 3 blocks of audio.
        assert segments[0].start_time == 0.0
        expected_offset = 3 * _BLOCK / _RATE
        assert abs(segments[1].start_time - expected_offset) < 1e-6

    def test_temp_wav_cleaned_up_after_stream(self) -> None:
        """The per-utterance temp WAV does not survive the stream."""
        speech = np.full(_BLOCK, 0.1, dtype=np.float32)
        silence = np.zeros(_BLOCK, dtype=np.float32)
        source = _ListSource([speech, speech, silence, silence])
        backend = _RecordingBackend()
        transcriber = RealtimeTranscriber(backend, segmenter=_fast_segmenter())

        list(transcriber.stream(source))

        assert not backend.received_paths[0].exists()


class TestAudioSourceProtocol:
    """The AudioSource protocol is satisfied structurally."""

    def test_list_source_is_audio_source(self) -> None:
        """A simple iterable-with-sample_rate satisfies AudioSource."""
        assert isinstance(_ListSource([], _RATE), AudioSource)

    def test_microphone_source_reports_sample_rate(self) -> None:
        """MicrophoneSource exposes its configured sample rate."""
        mic = MicrophoneSource(sample_rate=_RATE)
        assert mic.sample_rate == _RATE
        assert isinstance(mic, AudioSource)

    def test_microphone_without_sounddevice_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Iterating a MicrophoneSource without sounddevice raises ProcessingError."""
        import builtins

        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "sounddevice":
                raise ImportError("No module named 'sounddevice'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked_import)
        with pytest.raises(ProcessingError, match="sounddevice"):
            next(iter(MicrophoneSource()))
