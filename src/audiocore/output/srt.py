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

import re

from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult
from audiocore.output.timestamp import format_timestamp


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS,mmm (SRT uses a comma millisecond separator).

    Example:
        >>> _format_srt_timestamp(3725.678)
        '01:02:05,678'
        >>> _format_srt_timestamp(0.0)
        '00:00:00,000'
    """
    return format_timestamp(seconds, ms_separator=",")


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
        # Handle empty text gracefully, escape SRT-breaking sequences:
        # - Double newlines break cue structure
        # - "-->" is the SRT timestamp delimiter
        # - HTML entities for consistency with VTT output
        text = segment.text if segment.text else ""
        if text:
            text = (
                text.replace("-->", "- ->")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            text = re.sub(r"\n{2,}", "\n", text)

        # SRT cue format:
        # - Sequential number
        # - Start --> End timestamp
        # - Text content (may be multiline)
        # - Blank line separator
        cue = f"{i}\n{start_ts} --> {end_ts}\n{text}"
        cues.append(cue)

    # Join all cues with double newline, trailing newline for proper SRT spec
    return "\n\n".join(cues) + "\n"
