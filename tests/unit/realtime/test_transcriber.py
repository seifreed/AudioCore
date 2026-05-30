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
    Word,
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

    def test_audio_source_protocol_stub_returns_none(self) -> None:
        """The AudioSource protocol __iter__ body is an inert stub."""

        class _SuperDelegating(AudioSource):
            sample_rate = _RATE

            def __iter__(self):
                return super().__iter__()

        assert _SuperDelegating().__iter__() is None


def _install_fake_sounddevice(monkeypatch: pytest.MonkeyPatch, read_impl) -> None:
    """Register a minimal fake ``sounddevice`` module exposing InputStream."""
    import sys
    import types

    fake = types.ModuleType("sounddevice")

    class _InputStream:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

        def read(self, frames: int):
            return read_impl(frames)

    fake.InputStream = _InputStream  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", fake)


class TestMicrophoneCapture:
    """MicrophoneSource.__iter__ drives the sounddevice InputStream."""

    def test_stop_sets_stopped_flag(self) -> None:
        mic = MicrophoneSource()
        mic.stop()
        assert mic._stopped is True

    def test_iter_yields_blocks_until_stopped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def read_impl(frames: int):
            return np.zeros((frames, 1), dtype=np.float32), False

        _install_fake_sounddevice(monkeypatch, read_impl)
        mic = MicrophoneSource()

        it = iter(mic)
        first = next(it)
        assert first.dtype == np.float32
        assert first.ndim == 1

        mic.stop()
        with pytest.raises(StopIteration):
            next(it)

    def test_iter_reraises_processing_error_unwrapped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def read_impl(frames: int):
            raise ProcessingError("inner failure", context={})

        _install_fake_sounddevice(monkeypatch, read_impl)

        with pytest.raises(ProcessingError, match="inner failure"):
            next(iter(MicrophoneSource()))

    def test_iter_wraps_unexpected_capture_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def read_impl(frames: int):
            raise RuntimeError("device exploded")

        _install_fake_sounddevice(monkeypatch, read_impl)

        with pytest.raises(ProcessingError, match="Microphone capture failed") as exc_info:
            next(iter(MicrophoneSource()))
        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestShiftSegment:
    """_shift_segment offsets segment and word timings onto the stream timeline."""

    def test_shift_segment_without_words(self) -> None:
        from audiocore.realtime.transcriber import _shift_segment

        seg = Segment(start_time=0.0, end_time=0.5, text="hi", confidence=0.9)
        shifted = _shift_segment(seg, 2.0)

        assert shifted.start_time == 2.0
        assert shifted.end_time == 2.5
        assert shifted.words is None

    def test_shift_segment_with_words_offsets_each_word(self) -> None:
        from audiocore.realtime.transcriber import _shift_segment

        seg = Segment(
            start_time=0.0,
            end_time=1.0,
            text="hi there",
            confidence=0.9,
            words=[
                Word(word="hi", start_time=0.0, end_time=0.4, confidence=0.8),
                Word(word="there", start_time=0.5, end_time=1.0, confidence=0.7),
            ],
        )
        shifted = _shift_segment(seg, 3.0)

        assert shifted.words is not None
        assert shifted.words[0].start_time == 3.0
        assert shifted.words[0].end_time == 3.4
        assert shifted.words[1].start_time == 3.5
        assert shifted.words[1].word == "there"


class TestTranscribeRealtimeHelper:
    """transcribe_realtime resolves a backend and streams segments."""

    def test_uses_explicit_backend(self) -> None:
        from audiocore.realtime import transcribe_realtime

        backend = _RecordingBackend()
        # Empty source -> no utterances -> no transcription, just backend wiring.
        segments = list(transcribe_realtime(_ListSource([]), backend=backend))

        assert segments == []
        assert backend.received_paths == []

    def test_resolves_backend_from_config_when_omitted(self) -> None:
        from audiocore.config import AppConfig
        from audiocore.realtime import transcribe_realtime

        # Empty source -> backend is resolved from config but never invoked.
        segments = list(transcribe_realtime(_ListSource([]), backend=None, config=AppConfig()))

        assert segments == []
