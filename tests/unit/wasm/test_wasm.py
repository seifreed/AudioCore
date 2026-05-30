"""Regression tests for the WebAssembly (Pyodide) support surface (v2.0)."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from audiocore.models import Segment, Word
from audiocore.wasm import format_transcript, is_wasm, segments_from_data

_DICTS = [
    {"start_time": 0.0, "end_time": 1.5, "text": "Hello"},
    {"start_time": 1.5, "end_time": 3.0, "text": "world"},
]


class TestFormatTranscript:
    """format_transcript renders each format purely from segment data."""

    def test_srt_output(self) -> None:
        """SRT output includes indices and arrow-separated timestamps."""
        out = format_transcript(_DICTS, "srt")
        assert "1\n" in out
        assert "-->" in out
        assert "Hello" in out and "world" in out

    def test_vtt_output(self) -> None:
        """VTT output starts with the WEBVTT header."""
        out = format_transcript(_DICTS, "vtt")
        assert out.startswith("WEBVTT")

    def test_text_output(self) -> None:
        """Text output carries each segment's text."""
        out = format_transcript(_DICTS, "text")
        assert "Hello" in out
        assert "world" in out

    def test_json_output_round_trips(self) -> None:
        """JSON output is valid and preserves segment text."""
        out = format_transcript(_DICTS, "json")
        data = json.loads(out)
        assert [s["text"] for s in data["segments"]] == ["Hello", "world"]

    def test_accepts_segment_objects(self) -> None:
        """Segment instances are accepted alongside dicts."""
        segments = [Segment(start_time=0.0, end_time=1.0, text="hi")]
        out = format_transcript(segments, "text")
        assert "hi" in out

    def test_default_format_is_srt(self) -> None:
        """Omitting the format yields SRT."""
        assert "-->" in format_transcript(_DICTS)

    def test_invalid_format_raises(self) -> None:
        """An unknown format string is rejected."""
        with pytest.raises(ValueError, match="Invalid output format"):
            format_transcript(_DICTS, "doc")

    def test_explicit_duration_used_in_json(self) -> None:
        """An explicit duration overrides the segment-derived media duration."""
        out = format_transcript(_DICTS, "json", duration=42.0)
        assert json.loads(out)["media_info"]["duration"] == 42.0

    def test_words_preserved_in_json(self) -> None:
        """Word-level data passed in dict form survives into JSON output."""
        segments = [
            {
                "start_time": 0.0,
                "end_time": 1.0,
                "text": "hi",
                "words": [{"word": "hi", "start_time": 0.0, "end_time": 0.5}],
            }
        ]
        data = json.loads(format_transcript(segments, "json"))
        assert data["segments"][0]["words"][0]["word"] == "hi"


class TestSegmentsFromData:
    """segments_from_data normalizes mixed input into Segment models."""

    def test_mixed_input_normalized(self) -> None:
        """A mix of dicts and Segment objects becomes a list of Segments."""
        mixed = [Segment(start_time=0.0, end_time=1.0, text="a"), _DICTS[0]]
        result = segments_from_data(mixed)
        assert all(isinstance(s, Segment) for s in result)
        assert len(result) == 2

    def test_word_dict_normalized(self) -> None:
        """Nested word dicts validate into Word models."""
        result = segments_from_data(
            [
                {
                    "start_time": 0.0,
                    "end_time": 1.0,
                    "text": "hi",
                    "words": [{"word": "hi", "start_time": 0.0, "end_time": 1.0}],
                }
            ]
        )
        assert result[0].words is not None
        assert isinstance(result[0].words[0], Word)


class TestIsWasm:
    """is_wasm detects WebAssembly Python runtimes."""

    def test_false_on_native_cpython(self) -> None:
        """Under a normal interpreter, is_wasm() is False."""
        assert is_wasm() is False

    def test_true_when_pyodide_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """is_wasm() reports True when a pyodide module is present."""
        monkeypatch.setitem(sys.modules, "pyodide", object())
        assert is_wasm() is True


class TestWasmImportIsolation:
    """Importing audiocore.wasm must not pull native or backend dependencies.

    This is the core WebAssembly contract: the formatting surface has to load in
    a Pyodide runtime where torch, ctranslate2, ffmpeg, and the backends are
    unavailable.
    """

    def test_import_pulls_no_heavy_dependencies(self) -> None:
        """A clean interpreter importing audiocore.wasm loads no native deps."""
        code = (
            "import sys; import audiocore.wasm; "
            "forbidden = ['torch', 'ctranslate2', 'faster_whisper', 'openai', "
            "'numpy', 'scipy', 'audiocore.backends']; "
            "print(','.join(m for m in forbidden if m in sys.modules))"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
        )
        leaked = completed.stdout.strip()
        assert leaked == "", f"audiocore.wasm imported heavy modules: {leaked}"


class TestResolveDuration:
    """_resolve_duration falls back to the minimum when nothing else is known."""

    def test_empty_segments_and_no_duration_uses_minimum(self) -> None:
        from audiocore.models import MIN_MEDIA_DURATION_SECONDS
        from audiocore.wasm import _resolve_duration

        assert _resolve_duration([], None) == MIN_MEDIA_DURATION_SECONDS
