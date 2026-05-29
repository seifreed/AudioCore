"""Pluggable voice-activity-detection interface.

``VADModel`` is the structural contract a detector must satisfy to be used by
the pipeline. The bundled :class:`~audiocore.vad.silero.SileroVAD` implements
it, and callers may supply their own detector (WebRTC, an energy gate, a custom
ONNX/TorchScript model, ...) to :func:`~audiocore.vad.detect_speech` or the
``Pipeline`` without changing any pipeline code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from audiocore.vad.config import VADConfig


@runtime_checkable
class VADModel(Protocol):
    """Structural interface for a voice-activity detector.

    A detector takes a 16 kHz mono WAV path and returns raw speech spans as
    ``(start_time, end_time, confidence)`` tuples in seconds. Merge/split/pad
    post-processing is applied downstream by ``process_segments``, so an
    implementation only needs to report where speech is, not refine it.
    """

    def detect_file(
        self,
        audio_path: Path | str,
        config: VADConfig | None = None,
    ) -> list[tuple[float, float, float]]:
        """Return raw ``(start, end, confidence)`` speech spans for the file."""
        ...
