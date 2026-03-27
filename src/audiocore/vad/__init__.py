"""Voice Activity Detection using Silero VAD.

Provides high-level speech detection and segment processing.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from audiocore.vad.config import VADConfig
from audiocore.vad.segments import process_segments
from audiocore.vad.silero import SileroVAD

if TYPE_CHECKING:
    from audiocore.models import Segment

__all__ = [
    "VADConfig",
    "SileroVAD",
    "detect_speech",
    "process_segments",
]


def detect_speech(
    audio_path: str | Path,
    config: VADConfig | None = None,
    total_duration: float | None = None,
) -> list[Segment]:
    """Detect speech segments in audio file.

    High-level function that:
    1. Loads Silero VAD model (lazy, cached)
    2. Processes audio to find speech segments
    3. Applies VADConfig parameters for merge/split/pad
    4. Returns list of Segment models

    Args:
        audio_path: Path to 16kHz mono WAV file.
        config: VAD configuration (uses defaults if None).
        total_duration: Total audio duration in seconds (auto-detected if None).

    Returns:
        List of Segment objects with start_time, end_time, confidence.
        Text field is empty (filled by transcription pipeline).

    Raises:
        VADError: If model loading or processing fails.
        InvalidInputError: If file not found or invalid format.

    Example:
        >>> from audiocore.vad import detect_speech
        >>> segments = detect_speech("audio.wav")
        >>> for seg in segments:
        ...     print(f"{seg.start_time:.2f} - {seg.end_time:.2f}")
    """
    config = config or VADConfig()
    audio_path = Path(audio_path)

    if not audio_path.exists():
        from audiocore.errors import InvalidInputError

        raise InvalidInputError(
            f"Audio file not found: {audio_path}",
            context={"path": str(audio_path)},
            suggestions=["Check file path", "Ensure file exists"],
        )

    vad = SileroVAD()
    raw_segments = vad.detect_file(audio_path, config)

    # Get duration from probe if not provided
    if total_duration is None:
        from audiocore.media import probe

        media_info = probe(audio_path)
        total_duration = media_info.duration

    return process_segments(raw_segments, config, total_duration)
