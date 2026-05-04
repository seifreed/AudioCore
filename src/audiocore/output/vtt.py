"""VTT (WebVTT) subtitle formatter for transcription results.

Provides WebVTT format output compatible with web video players:
- WEBVTT header at the start
- Timestamps in HH:MM:SS.mmm format (dot for milliseconds)
- Cue blocks with timestamp lines and text content
- No sequential numbering (unlike SRT)

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
    >>> print(format_vtt(result, TranscriptionOptions()))
    WEBVTT

    00:00:00.000 --> 00:00:05.234
    Hello world

    00:00:05.500 --> 00:00:10.000
    How are you?
    <BLANKLINE>
"""

from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult


def _format_vtt_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for VTT format.

    VTT uses a period (.) as the milliseconds separator, unlike SRT which uses
    a comma (,). This function converts floating-point seconds to the standard
    VTT timestamp format.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted timestamp string with zero-padded hours, minutes, seconds
        and milliseconds using period separator (e.g., "01:23:45.678").

    Example:
        >>> _format_vtt_timestamp(3725.678)
        '01:02:05.678'
        >>> _format_vtt_timestamp(0.0)
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


def format_vtt(result: TranscriptionResult, options: TranscriptionOptions) -> str:
    """Format transcription result as VTT subtitles.

    Produces WebVTT format output compatible with web video players:
    - WEBVTT file signature at the start
    - Timestamps in HH:MM:SS.mmm format (period separator)
    - No sequential numbering (cues identified by timestamp)
    - Each cue followed by a blank line separator

    Empty segments return just the WEBVTT header. Empty text in segments
    produces a cue with empty text content. UTF-8 encoding is always used.

    Args:
        result: TranscriptionResult containing segments and metadata.
        options: TranscriptionOptions (used for consistency with other formatters).

    Returns:
        VTT formatted string with WEBVTT header and cue blocks.
        Empty segments return just "WEBVTT".

    Example:
        >>> result = TranscriptionResult(...)
        >>> vtt = format_vtt(result, TranscriptionOptions())
        >>> print(vtt)
        WEBVTT

        00:00:00.000 --> 00:00:05.234
        Hello world

        00:00:05.500 --> 00:00:10.000
        How are you?
        <BLANKLINE>
    """
    # VTT always starts with WEBVTT header
    if not result.segments:
        return "WEBVTT\n\n"

    cue_blocks = []

    for segment in result.segments:
        start_ts = _format_vtt_timestamp(segment.start_time)
        end_ts = _format_vtt_timestamp(segment.end_time)
        # Handle empty text gracefully, escape WebVTT-breaking sequences
        # Double newlines break cue structure — collapse them
        text = segment.text if segment.text else ""
        if text:
            text = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n\n", "\n")
                .replace("-->", "- ->")
            )

        # VTT cue format:
        # - No sequential numbering (unlike SRT)
        # - Start --> End timestamp
        # - Text content (may be multiline)
        # - Blank line separator
        cue_block = f"{start_ts} --> {end_ts}\n{text}"
        cue_blocks.append(cue_block)

    # WEBVTT header, double newline, then cue blocks separated by blank lines
    # Trailing newline for proper VTT spec
    return "WEBVTT\n\n" + "\n\n".join(cue_blocks) + "\n"
