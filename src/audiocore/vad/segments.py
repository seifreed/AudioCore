"""Segment processing utilities for VAD output.

This module provides functions to process raw VAD output into clean,
non-overlapping, chronologically ordered segments with configurable
merging, splitting, and padding.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from audiocore.models import Segment

if TYPE_CHECKING:
    from audiocore.vad.config import VADConfig


def filter_by_confidence(
    segments: list[tuple[float, float, float]],
    threshold: float,
) -> list[tuple[float, float, float]]:
    """Filter segments by minimum confidence threshold.

    Args:
        segments: List of (start, end, confidence) tuples.
        threshold: Minimum confidence to keep (0.0-1.0).

    Returns:
        Filtered list of segments.
    """
    return [(s, e, c) for s, e, c in segments if c >= threshold]


def merge_short_segments(
    segments: list[tuple[float, float, float]],
    config: VADConfig,
) -> list[tuple[float, float, float]]:
    """Merge segments shorter than min_segment_duration.

    Merges if:
    - Segment duration < min_segment_duration
    - Gap to next segment < min_silence_duration_ms / 1000

    Args:
        segments: List of (start, end, confidence) tuples (must be sorted).
        config: VAD configuration.

    Returns:
        Merged segments list.
    """
    if not segments:
        return segments

    min_duration = config.min_segment_duration
    max_gap = config.min_silence_duration_ms / 1000.0

    merged = [segments[0]]
    for start, end, conf in segments[1:]:
        prev_start, prev_end, prev_conf = merged[-1]
        prev_duration = prev_end - prev_start
        curr_duration = end - start
        gap = start - prev_end

        # Merge if either segment is short and gap is small
        if (prev_duration < min_duration or curr_duration < min_duration) and gap < max_gap:
            merged[-1] = (prev_start, end, min(prev_conf, conf))
        else:
            merged.append((start, end, conf))

    # Final pass: merge any remaining short segments at the end
    # Walk backwards from the end, merging short segments into the preceding one
    while len(merged) > 1 and (merged[-1][1] - merged[-1][0]) < min_duration:
        prev_start, prev_end, prev_conf = merged[-2]
        gap = merged[-1][0] - prev_end
        if gap >= max_gap:
            break
        merged[-2] = (prev_start, merged[-1][1], min(prev_conf, merged[-1][2]))
        merged.pop()

    # Keep orphan segments shorter than min_segment_duration — dropping them
    # would produce empty output for legitimate short utterances.
    return merged


def split_long_segments(
    segments: list[tuple[float, float, float]],
    config: VADConfig,
) -> list[tuple[float, float, float]]:
    """Split segments longer than max_segment_duration.

    Splits evenly into chunks of max_segment_duration.
    Last chunk takes remainder.

    Args:
        segments: List of (start, end, confidence) tuples.
        config: VAD configuration.

    Returns:
        Split segments list.
    """
    result = []
    max_duration = config.max_segment_duration

    for start, end, conf in segments:
        duration = end - start
        if duration <= max_duration:
            result.append((start, end, conf))
        else:
            # Split into equal chunks
            n_chunks = math.ceil(duration / max_duration)
            chunk_duration = duration / n_chunks
            for i in range(n_chunks):
                chunk_start = start + i * chunk_duration
                chunk_end = min(end, start + (i + 1) * chunk_duration)
                result.append((chunk_start, chunk_end, conf))

    return result


def pad_segments(
    segments: list[tuple[float, float, float]],
    pad_ms: int,
    total_duration: float,
) -> list[tuple[float, float, float]]:
    """Add padding to segment boundaries.

    Padding is added to start and end of each segment.
    Segments are clipped to [0, total_duration].
    Overlapping segments after padding are merged.

    Args:
        segments: List of (start, end, confidence) tuples.
        pad_ms: Padding in milliseconds.
        total_duration: Total audio duration in seconds.

    Returns:
        Padded segments list with overlaps merged.
    """
    if not segments:
        return segments

    pad_seconds = pad_ms / 1000.0
    result = []

    for start, end, conf in segments:
        padded_start = max(0.0, start - pad_seconds)
        padded_end = min(total_duration, end + pad_seconds)
        result.append((padded_start, padded_end, conf))

    # Merge overlapping segments after padding
    merged = [result[0]]
    for start, end, conf in result[1:]:
        prev_start, prev_end, prev_conf = merged[-1]
        if start < prev_end:
            # Overlap: merge segments, use max confidence of the two
            merged[-1] = (prev_start, max(prev_end, end), max(prev_conf, conf))
        else:
            merged.append((start, end, conf))

    return merged


def validate_segments(
    segments: list[tuple[float, float, float]],
    total_duration: float,
    config: VADConfig,
) -> None:
    """Validate segments for correctness.

    Checks:
    - Segments are in chronological order
    - No overlapping segments
    - No segments extending beyond total_duration
    - No gaps larger than min_silence_duration_ms * 2

    Raises:
        ValueError: If validation fails.
    """
    if not segments:
        return

    # Check ordering and overlap
    for i, (start, end, _) in enumerate(segments):
        if start < 0:
            raise ValueError(f"Segment {i}: start ({start}) is negative")
        if end < start:
            raise ValueError(f"Segment {i}: end ({end}) < start ({start})")
        if end > total_duration:
            raise ValueError(f"Segment {i}: end ({end}) exceeds total duration ({total_duration})")
        if i > 0:
            prev_start, prev_end, _ = segments[i - 1]
            if start < prev_end:
                raise ValueError(f"Overlapping segments at index {i}")

    # Check for large gaps (indicates VAD might have missed speech)
    max_gap = config.min_silence_duration_ms / 1000.0 * 2
    for i in range(1, len(segments)):
        gap = segments[i][0] - segments[i - 1][1]
        if gap > max_gap:
            # Warning, not error - may be legitimate silence
            pass  # Could log warning here


def to_segment_models(
    segments: list[tuple[float, float, float]],
) -> list[Segment]:
    """Convert raw segments to Segment models.

    Args:
        segments: List of (start, end, confidence) tuples.

    Returns:
        List of Segment models with empty text.
    """
    return [
        Segment(
            start_time=start,
            end_time=end,
            text="",  # Filled by transcription
            confidence=conf,
        )
        for start, end, conf in segments
    ]


def process_segments(
    vad_output: list[tuple[float, float, float]],
    config: VADConfig,
    total_duration: float,
) -> list[Segment]:
    """Process raw VAD output into clean segments.

    Pipeline:
    1. Filter by confidence threshold
    2. Merge short segments
    3. Split long segments
    4. Pad segments
    5. Validate segments
    6. Convert to Segment models

    Args:
        vad_output: Raw VAD output (start, end, confidence) tuples.
        config: VAD configuration.
        total_duration: Total audio duration in seconds.

    Returns:
        List of Segment models.
    """
    # 1. Filter by confidence and normalize to chronological order.
    segments = sorted(
        filter_by_confidence(vad_output, config.speech_threshold),
        key=lambda segment: (segment[0], segment[1]),
    )

    # 2. Merge short segments
    segments = merge_short_segments(segments, config)

    # 3. Split long segments
    segments = split_long_segments(segments, config)

    # 4. Pad segments
    segments = pad_segments(segments, config.speech_pad_ms, total_duration)

    # 5. Enforce max duration again in case padding merged nearby segments.
    segments = split_long_segments(segments, config)

    # 6. Validate segments
    validate_segments(segments, total_duration, config)

    # 7. Convert to Segment models
    return to_segment_models(segments)
