"""WebAssembly (Pyodide) support: a browser-safe formatting surface.

AudioCore's transcription engine depends on native, non-browser components
(ffmpeg as a subprocess, PyTorch + CTranslate2 for local inference, and HTTP
calls to OpenAI) that cannot run inside a WebAssembly runtime. What *is*
portable is the pure-Python tail of the pipeline: the result models and the
output formatters, which have no dependency beyond pydantic.

This module is the supported entry point for those environments. It imports
only pure-Python pieces — importing ``audiocore.wasm`` never pulls in torch,
ctranslate2, ffmpeg, the OpenAI client, or any backend — so a Pyodide app can
take timing+text data produced elsewhere (e.g. a JS-side ``whisper.cpp`` WASM
build, or a transcription API response) and render text/JSON/SRT/VTT subtitles
entirely in the browser.

Example (in a Pyodide REPL):
    >>> from audiocore.wasm import format_transcript
    >>> segments = [
    ...     {"start_time": 0.0, "end_time": 1.5, "text": "Hello"},
    ...     {"start_time": 1.5, "end_time": 3.0, "text": "world"},
    ... ]
    >>> print(format_transcript(segments, "srt"))
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence

from audiocore.models import (
    MIN_MEDIA_DURATION_SECONDS,
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
)
from audiocore.output.json import format_json
from audiocore.output.srt import format_srt
from audiocore.output.text import format_text
from audiocore.output.vtt import format_vtt
from audiocore.types import BackendType, OutputFormat

__all__ = [
    "is_wasm",
    "format_transcript",
    "segments_from_data",
]

# Formatter dispatch — kept local so this module never imports the pipeline.
_FORMATTERS = {
    OutputFormat.TEXT: format_text,
    OutputFormat.JSON: format_json,
    OutputFormat.SRT: format_srt,
    OutputFormat.VTT: format_vtt,
}


def is_wasm() -> bool:
    """Return True when running under a WebAssembly Python runtime.

    Detects Pyodide / Emscripten-hosted CPython, where native backends and
    subprocesses are unavailable and only this module's pure formatting surface
    should be used.
    """
    return sys.platform == "emscripten" or "pyodide" in sys.modules


def segments_from_data(segments: Sequence[Segment | Mapping[str, object]]) -> list[Segment]:
    """Normalize segment data (dicts or Segment objects) into Segment models.

    Args:
        segments: A sequence of ``Segment`` instances or mappings with at least
            ``start_time``, ``end_time``, and ``text`` (``confidence``, ``words``,
            and ``speaker`` are optional).

    Returns:
        A list of validated ``Segment`` models.

    Raises:
        pydantic.ValidationError: If a mapping does not satisfy the Segment model.
    """
    normalized: list[Segment] = []
    for item in segments:
        if isinstance(item, Segment):
            normalized.append(item)
        else:
            normalized.append(Segment.model_validate(dict(item)))
    return normalized


def format_transcript(
    segments: Sequence[Segment | Mapping[str, object]],
    output_format: OutputFormat | str = OutputFormat.SRT,
    *,
    duration: float | None = None,
) -> str:
    """Format transcript segments into text, JSON, SRT, or VTT in the browser.

    This is a pure, dependency-free operation suitable for WebAssembly: it takes
    already-produced segment timing/text and renders the requested format using
    the same formatters as the native pipeline.

    Args:
        segments: Segment objects or mappings (see :func:`segments_from_data`).
        output_format: Target format as an ``OutputFormat`` or string
            (``"text"``, ``"json"``, ``"srt"``, ``"vtt"``).
        duration: Optional media duration in seconds for the JSON ``media_info``.
            Defaults to the last segment's end time.

    Returns:
        The formatted transcript as a string.

    Raises:
        ValueError: If ``output_format`` is not a recognized format.
    """
    resolved_format = (
        output_format
        if isinstance(output_format, OutputFormat)
        else OutputFormat.parse(output_format)
    )
    normalized = segments_from_data(segments)
    media_duration = _resolve_duration(normalized, duration)

    options = TranscriptionOptions(output_format=resolved_format)
    result = TranscriptionResult(
        segments=normalized,
        media_info=MediaInfo(duration=media_duration, format="wasm"),
        config_used=options,
        processing_time_seconds=0.0,
        backend_used=BackendType.AUTO,
    )
    return _FORMATTERS[resolved_format](result, options)


def _resolve_duration(segments: list[Segment], duration: float | None) -> float:
    """Resolve a media duration from an explicit value or the segment timeline."""
    if duration is not None and duration > 0:
        return duration
    if segments:
        return max(segment.end_time for segment in segments)
    return MIN_MEDIA_DURATION_SECONDS
