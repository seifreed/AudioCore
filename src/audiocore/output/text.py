"""Plain text formatter for transcription results.

Provides timestamped text output in format:
[HH:MM:SS.mmm] text

Example:
    >>> from audiocore.models import Segment, MediaInfo, TranscriptionResult, TranscriptionOptions
    >>> result = TranscriptionResult(
    ...     segments=[
    ...         Segment(start_time=0.0, end_time=5.234, text="Hello world"),
    ...         Segment(start_time=5.5, end_time=10.0, text="How are you?"),
    ...     ],
    ...     media_info=MediaInfo(...),
    ...     config_used=TranscriptionOptions(),
    ...     processing_time_seconds=15.5,
    ...     backend_used=BackendType.OPENAI
    ... )
    >>> format_text(result, TranscriptionOptions())
    '[00:00:00.000] Hello world\\n[00:00:05.500] How are you?'
"""

from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string with zero-padded hours, minutes, seconds
        and milliseconds (e.g., "01:23:45.678").

    Example:
        >>> _format_timestamp(3725.678)
        '01:02:05.678'
        >>> _format_timestamp(0.0)
        '00:00:00.000'
    """
    total_ms = max(0, round(seconds * 1000))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    secs = total_ms // 1_000
    millis = total_ms % 1_000

    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def format_text(result: TranscriptionResult, options: TranscriptionOptions) -> str:
    """Format transcription result as timestamped plain text.

    Each segment is output on its own line with a timestamp prefix:
    [HH:MM:SS.mmm] transcribed text

    Empty text segments are handled gracefully with empty content after
    the timestamp. UTF-8 encoding is always used for text content.

    Args:
        result: TranscriptionResult containing segments and metadata.
        options: TranscriptionOptions (used for consistency with other formatters).

    Returns:
        UTF-8 encoded string with transcript segments, one per line.

    Example:
        >>> result = TranscriptionResult(...)
        >>> text = format_text(result, TranscriptionOptions())
        >>> print(text)
        [00:00:00.000] Hello world
        [00:00:05.500] How are you?
        [00:00:10.250] I'm doing great
    """
    lines = []

    for segment in result.segments:
        timestamp = _format_timestamp(segment.start_time)
        # Handle empty text gracefully
        text = segment.text if segment.text else ""
        lines.append(f"[{timestamp}] {text}")

    return "\n".join(lines)
