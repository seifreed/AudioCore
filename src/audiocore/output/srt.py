"""SRT (SubRip) subtitle formatter for transcription results.

Provides SRT format output compatible with video players:
- Sequential numbering starting from 1
- Timestamps in HH:MM:SS,mmm format (comma for milliseconds)
- Text content with blank line separators

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
    >>> print(format_srt(result, TranscriptionOptions()))
    1
    00:00:00,000 --> 00:00:05,234
    Hello world

    2
    00:00:05,500 --> 00:00:10,000
    How are you?
    <BLANKLINE>
"""

from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm for SRT format.

    SRT uses comma (,) as the milliseconds separator, unlike VTT which uses
    a period (.). This function converts floating-point seconds to the
    standard SRT timestamp format.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string with zero-padded hours, minutes, seconds
        and milliseconds using comma separator (e.g., "01:23:45,678").

    Example:
        >>> _format_srt_timestamp(3725.678)
        '01:02:05,678'
        >>> _format_srt_timestamp(0.0)
        '00:00:00,000'
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = round((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_srt(result: TranscriptionResult, options: TranscriptionOptions) -> str:
    """Format transcription result as SRT subtitles.

    Produces SRT format output compatible with most video players:
    - Sequential numbering starting from 1
    - Timestamps in HH:MM:SS,mmm format (comma separator)
    - Each cue followed by a blank line separator

    Empty segments return an empty string. Empty text in segments produces
    a cue with empty text content. UTF-8 encoding is always used for text.

    Args:
        result: TranscriptionResult containing segments and metadata.
        options: TranscriptionOptions (used for consistency with other formatters).

    Returns:
        SRT formatted string with sequential cues. Empty segments return
        an empty string.

    Example:
        >>> result = TranscriptionResult(...)
        >>> srt = format_srt(result, TranscriptionOptions())
        >>> print(srt)
        1
        00:00:00,000 --> 00:00:05,234
        Hello world

        2
        00:00:05,500 --> 00:00:10,000
        How are you?
        <BLANKLINE>
    """
    if not result.segments:
        return ""

    cues = []

    for i, segment in enumerate(result.segments, start=1):
        start_ts = _format_srt_timestamp(segment.start_time)
        end_ts = _format_srt_timestamp(segment.end_time)
        # Handle empty text gracefully
        text = segment.text if segment.text else ""

        # SRT cue format:
        # - Sequential number
        # - Start --> End timestamp
        # - Text content (may be multiline)
        # - Blank line separator
        cue = f"{i}\n{start_ts} --> {end_ts}\n{text}"
        cues.append(cue)

    # Join all cues with double newline, trailing newline for proper SRT spec
    return "\n\n".join(cues) + "\n"
