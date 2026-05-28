"""Shared timestamp formatting for output formatters.

Subtitle and text formatters all render seconds as a zero-padded
HH:MM:SS<sep>mmm timestamp; only the millisecond separator differs (SRT uses
a comma, VTT and plain text use a period). This module owns that conversion.
"""

from __future__ import annotations

_MS_PER_HOUR = 3_600_000
_MS_PER_MINUTE = 60_000
_MS_PER_SECOND = 1_000


def format_timestamp(seconds: float, *, ms_separator: str = ".") -> str:
    """Format seconds as a zero-padded HH:MM:SS<sep>mmm timestamp.

    Negative inputs clamp to zero. Pass ms_separator="," for SRT; the default
    "." suits VTT and plain text.

    Example:
        >>> format_timestamp(3725.678)
        '01:02:05.678'
        >>> format_timestamp(3725.678, ms_separator=",")
        '01:02:05,678'
        >>> format_timestamp(0.0)
        '00:00:00.000'
    """
    total_ms = max(0, round(seconds * 1000))
    hours = total_ms // _MS_PER_HOUR
    total_ms %= _MS_PER_HOUR
    minutes = total_ms // _MS_PER_MINUTE
    total_ms %= _MS_PER_MINUTE
    secs = total_ms // _MS_PER_SECOND
    millis = total_ms % _MS_PER_SECOND
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{ms_separator}{millis:03d}"
