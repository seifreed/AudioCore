"""Unit tests for segment processing functions.

Tests for filter_by_confidence, merge_short_segments, split_long_segments,
pad_segments, validate_segments, to_segment_models, and process_segments.
"""

import pytest

from audiocore.models import Segment
from audiocore.vad.config import VADConfig
from audiocore.vad.segments import (
    filter_by_confidence,
    merge_short_segments,
    pad_segments,
    process_segments,
    split_long_segments,
    to_segment_models,
    validate_segments,
)

# =============================================================================
# Test fixtures
# =============================================================================


@pytest.fixture
def default_config() -> VADConfig:
    """Default VADConfig for testing."""
    return VADConfig()


@pytest.fixture
def short_segment_config() -> VADConfig:
    """Config with short max duration for testing splits."""
    return VADConfig(
        min_segment_duration=0.3,
        max_segment_duration=5.0,
        speech_threshold=0.5,
        silence_threshold=0.3,
        speech_pad_ms=30,
        min_silence_duration_ms=100,
        window_size_samples=512,
    )


@pytest.fixture
def sample_vad_output() -> list[tuple[float, float, float]]:
    """Sample VAD output tuples for testing."""
    return [
        (0.0, 1.5, 0.85),
        (2.0, 4.5, 0.75),
        (5.0, 8.0, 0.90),
    ]


@pytest.fixture
def low_confidence_segments() -> list[tuple[float, float, float]]:
    """Segments with varying confidence levels."""
    return [
        (0.0, 1.0, 0.95),
        (2.0, 3.0, 0.45),
        (4.0, 5.0, 0.60),
        (6.0, 7.0, 0.30),
    ]


@pytest.fixture
def short_segments() -> list[tuple[float, float, float]]:
    """Very short segments for merge testing."""
    return [
        (0.0, 0.2, 0.80),  # 0.2s, short
        (0.25, 1.0, 0.75),  # Will merge with above
        (2.0, 3.0, 0.85),
    ]


@pytest.fixture
def long_segment() -> list[tuple[float, float, float]]:
    """Single long segment for split testing."""
    return [(0.0, 45.0, 0.88)]


# =============================================================================
# filter_by_confidence tests
# =============================================================================


class TestFilterByConfidence:
    """Tests for filter_by_confidence function."""

    def test_filter_removes_low_confidence_segments(
        self, low_confidence_segments: list[tuple[float, float, float]]
    ) -> None:
        """Segments below threshold should be removed."""
        result = filter_by_confidence(low_confidence_segments, threshold=0.5)
        # Should keep segments with confidence >= 0.5
        assert len(result) == 2
        assert all(conf >= 0.5 for _, _, conf in result)

    def test_filter_keeps_high_confidence_segments(
        self, sample_vad_output: list[tuple[float, float, float]]
    ) -> None:
        """Segments at or above threshold should be kept."""
        result = filter_by_confidence(sample_vad_output, threshold=0.5)
        assert len(result) == len(sample_vad_output)

    def test_filter_empty_segments_returns_empty(self) -> None:
        """Empty input should return empty output."""
        result = filter_by_confidence([], threshold=0.5)
        assert result == []

    def test_filter_with_threshold_0_keeps_all(
        self, sample_vad_output: list[tuple[float, float, float]]
    ) -> None:
        """Threshold of 0 should keep all segments."""
        result = filter_by_confidence(sample_vad_output, threshold=0.0)
        assert len(result) == len(sample_vad_output)

    def test_filter_with_threshold_1_removes_all_if_all_below(
        self, sample_vad_output: list[tuple[float, float, float]]
    ) -> None:
        """Threshold of 1 should remove all segments if none have perfect confidence."""
        result = filter_by_confidence(sample_vad_output, threshold=1.0)
        assert len(result) == 0


# =============================================================================
# merge_short_segments tests
# =============================================================================


class TestMergeShortSegments:
    """Tests for merge_short_segments function."""

    def test_merge_combines_short_segments_with_small_gap(self, default_config: VADConfig) -> None:
        """Short segments with small gaps should merge."""
        # 0.2s gap (150ms) < min_silence_duration (100ms/1000 = 0.1s)? No, gap is larger
        # Let's use gap < 0.1s which is min_silence_duration_ms / 1000
        segments = [
            (0.0, 0.2, 0.80),  # 0.2s, short
            (0.25, 1.0, 0.75),  # 0.05s gap < 0.1s, will merge
        ]
        result = merge_short_segments(segments, default_config)
        assert len(result) == 1
        assert result[0][0] == 0.0
        assert result[0][1] == 1.0
        assert result[0][2] == 0.75  # min confidence

    def test_merge_does_not_combine_long_segments(self, default_config: VADConfig) -> None:
        """Long segments should not merge."""
        segments = [
            (0.0, 2.0, 0.80),  # 2s duration, not short
            (2.1, 4.0, 0.75),  # 1.9s duration, not short
        ]
        result = merge_short_segments(segments, default_config)
        assert len(result) == 2

    def test_merge_does_not_combine_segments_with_large_gap(
        self, default_config: VADConfig
    ) -> None:
        """Segments with large gaps should not merge."""
        # min_silence_duration_ms = 100, so max_gap = 0.1s
        segments = [
            (0.0, 0.2, 0.80),  # Short
            (1.0, 2.0, 0.75),  # Gap is 0.8s > 0.1s, won't merge
        ]
        result = merge_short_segments(segments, default_config)
        # First segment may still try to merge if it's short, but gap > max_gap
        # Actually the first segment (0.2s < 0.5s min) should try to merge
        # but gap (0.8s) > 0.1s, so it won't merge
        assert len(result) == 2

    def test_merge_empty_returns_empty(self, default_config: VADConfig) -> None:
        """Empty input should return empty."""
        result = merge_short_segments([], default_config)
        assert result == []

    def test_merge_preserves_confidence_as_minimum(self, default_config: VADConfig) -> None:
        """Merged segment should have minimum confidence."""
        segments = [
            (0.0, 0.3, 0.90),  # Short, will merge
            (0.35, 1.0, 0.60),  # Small gap < 0.1s
        ]
        result = merge_short_segments(segments, default_config)
        assert len(result) == 1
        assert result[0][2] == 0.60  # min(0.90, 0.60)

    def test_merge_single_segment_returns_single(self, default_config: VADConfig) -> None:
        """Single segment input should return single segment."""
        segments = [(0.0, 2.0, 0.80)]
        result = merge_short_segments(segments, default_config)
        assert len(result) == 1
        assert result == segments

    def test_merge_final_short_segment_merges_with_previous(
        self, default_config: VADConfig
    ) -> None:
        """Final short segment should merge with previous if gap is small."""
        segments = [
            (0.0, 1.0, 0.80),  # Long enough
            (1.05, 2.0, 0.75),  # Long enough
            (2.05, 2.20, 0.70),  # Short, should merge with previous
        ]
        result = merge_short_segments(segments, default_config)
        # Last segment is 0.15s, short, gap is 0.05s < 0.1s
        assert len(result) == 2

    def test_merge_single_orphan_short_segment_dropped(self, default_config: VADConfig) -> None:
        """Regression: single short segment below min_segment_duration is dropped.

        Previously, merge_short_segments would keep a single short segment
        that couldn't be merged with any neighbor, producing noisy output.
        """
        segments = [(0.0, 0.1, 0.80)]  # 0.1s, well below default min 0.5s
        result = merge_short_segments(segments, default_config)
        assert result == []

    def test_merge_single_long_segment_kept(self, default_config: VADConfig) -> None:
        """A single segment at or above min_segment_duration should be kept."""
        segments = [(0.0, 1.0, 0.80)]  # 1.0s, above default min 0.5s
        result = merge_short_segments(segments, default_config)
        assert len(result) == 1


# =============================================================================
# split_long_segments tests
# =============================================================================


class TestSplitLongSegments:
    """Tests for split_long_segments function."""

    def test_split_does_not_split_short_segment(self, default_config: VADConfig) -> None:
        """Segment within max duration should not be split."""
        segments = [(0.0, 5.0, 0.80)]  # 5s < 30s default max
        result = split_long_segments(segments, default_config)
        assert len(result) == 1
        assert result == segments

    def test_split_divides_long_segment_evenly(self) -> None:
        """Long segment should be split into even chunks."""
        config = VADConfig(max_segment_duration=10.0)
        segments = [(0.0, 45.0, 0.88)]  # 45s, should split into 5 chunks
        result = split_long_segments(segments, config)
        assert len(result) == 5
        # Each chunk should be 9s
        for i, (start, end, conf) in enumerate(result):
            expected_dur = 9.0
            assert abs((end - start) - expected_dur) < 0.01
            assert conf == 0.88

    def test_split_multiple_segments(self) -> None:
        """Multiple segments should be processed correctly."""
        config = VADConfig(max_segment_duration=5.0)
        segments = [
            (0.0, 3.0, 0.80),  # Not split
            (5.0, 15.0, 0.75),  # Split into 2 chunks (10s / 5s)
            (20.0, 25.0, 0.90),  # Not split (exactly 5s, at limit)
        ]
        result = split_long_segments(segments, config)
        assert len(result) == 4  # 1 + 2 + 1
        # Check first (unchanged)
        assert result[0] == (0.0, 3.0, 0.80)
        # Check second (split into 2 chunks of 5s each)
        assert result[1][0] == 5.0
        assert result[1][1] == 10.0
        assert result[1][2] == 0.75
        assert result[2][2] == 0.75

    def test_split_preserves_confidence(self) -> None:
        """Split segments should preserve original confidence."""
        config = VADConfig(max_segment_duration=10.0)
        segments = [(0.0, 45.0, 0.92)]
        result = split_long_segments(segments, config)
        for _, _, conf in result:
            assert conf == 0.92

    def test_split_handles_just_over_threshold(self) -> None:
        """Segment just over threshold should split into 2."""
        config = VADConfig(max_segment_duration=10.0)
        segments = [(0.0, 10.1, 0.80)]  # Just over 10s
        result = split_long_segments(segments, config)
        assert len(result) == 2


# =============================================================================
# pad_segments tests
# =============================================================================


class TestPadSegments:
    """Tests for pad_segments function."""

    def test_pad_adds_padding_to_start_and_end(self) -> None:
        """Padding should be added to both ends."""
        segments = [(1.0, 2.0, 0.80)]
        result = pad_segments(segments, pad_ms=100, total_duration=5.0)
        assert len(result) == 1
        start, end, conf = result[0]
        # 100ms = 0.1s padding
        assert start == 0.9
        assert end == 2.1
        assert conf == 0.80

    def test_pad_does_not_go_below_zero(self) -> None:
        """Padding should not go below 0."""
        segments = [(0.05, 1.0, 0.80)]
        result = pad_segments(segments, pad_ms=100, total_duration=5.0)
        assert result[0][0] == 0.0  # Clamped at 0

    def test_pad_does_not_exceed_total_duration(self) -> None:
        """Padding should not exceed total duration."""
        segments = [(4.0, 4.9, 0.80)]
        result = pad_segments(segments, pad_ms=100, total_duration=5.0)
        assert result[0][1] == 5.0  # Clamped at total_duration

    def test_pad_zero_preserves_segment(self) -> None:
        """Zero padding should preserve segment unchanged."""
        segments = [(1.0, 2.5, 0.75)]
        result = pad_segments(segments, pad_ms=0, total_duration=10.0)
        assert result == segments

    def test_pad_multiple_segments(self) -> None:
        """Multiple segments should each get padding."""
        segments = [
            (1.0, 2.0, 0.80),
            (3.0, 4.5, 0.75),
        ]
        result = pad_segments(segments, pad_ms=50, total_duration=10.0)
        assert len(result) == 2
        # 50ms = 0.05s
        assert result[0][0] == 0.95
        assert result[0][1] == 2.05
        assert result[1][0] == 2.95
        assert result[1][1] == 4.55


# =============================================================================
# validate_segments tests
# =============================================================================


class TestValidateSegments:
    """Tests for validate_segments function."""

    def test_validate_passes_correct_segments(self, default_config: VADConfig) -> None:
        """Valid segments should pass validation."""
        segments = [
            (0.0, 1.0, 0.80),
            (1.5, 3.0, 0.75),
        ]
        # Should not raise
        validate_segments(segments, total_duration=10.0, config=default_config)

    def test_validate_raises_for_end_before_start(self, default_config: VADConfig) -> None:
        """Segment with end < start should raise."""
        segments = [(1.0, 0.5, 0.80)]
        with pytest.raises(ValueError, match="end.*<.*start"):
            validate_segments(segments, total_duration=10.0, config=default_config)

    def test_validate_raises_for_overlapping_segments(self, default_config: VADConfig) -> None:
        """Overlapping segments should raise."""
        segments = [
            (0.0, 2.0, 0.80),
            (1.5, 3.0, 0.75),  # Overlaps with first
        ]
        with pytest.raises(ValueError, match="Overlapping"):
            validate_segments(segments, total_duration=10.0, config=default_config)

    def test_validate_allows_reasonable_gaps(self, default_config: VADConfig) -> None:
        """Gaps between segments should be allowed."""
        segments = [
            (0.0, 1.0, 0.80),
            (5.0, 6.0, 0.75),  # 4s gap
        ]
        # Should not raise (gap is allowed)
        validate_segments(segments, total_duration=10.0, config=default_config)

    def test_validate_empty_segments_passes(self, default_config: VADConfig) -> None:
        """Empty list should pass validation."""
        validate_segments([], total_duration=10.0, config=default_config)

    def test_validate_raises_for_segment_exceeding_duration(self, default_config: VADConfig) -> None:
        """Regression: segment end_time exceeding total_duration must raise.

        Previously, validate_segments accepted total_duration but never
        validated that segments don't extend beyond it.
        """
        segments = [(0.0, 15.0, 0.80)]
        with pytest.raises(ValueError, match="exceeds total duration"):
            validate_segments(segments, total_duration=10.0, config=default_config)


# =============================================================================
# to_segment_models tests
# =============================================================================


class TestToSegmentModels:
    """Tests for to_segment_models function."""

    def test_to_segment_models_converts_tuples(self) -> None:
        """Should convert tuples to Segment models."""
        segments = [
            (0.0, 1.0, 0.85),
            (2.0, 3.5, 0.70),
        ]
        result = to_segment_models(segments)
        assert len(result) == 2
        assert all(isinstance(s, Segment) for s in result)
        assert result[0].start_time == 0.0
        assert result[0].end_time == 1.0
        assert result[0].confidence == 0.85

    def test_to_segment_models_empty_returns_empty(self) -> None:
        """Empty input should return empty list."""
        result = to_segment_models([])
        assert result == []

    def test_to_segment_models_has_empty_text(self) -> None:
        """Segment models should have empty text field."""
        segments = [(0.0, 1.0, 0.80)]
        result = to_segment_models(segments)
        assert result[0].text == ""


# =============================================================================
# process_segments integration tests
# =============================================================================


class TestProcessSegments:
    """Integration tests for process_segments function."""

    def test_process_segments_runs_full_pipeline(self, default_config: VADConfig) -> None:
        """Should apply all processing steps."""
        # Raw VAD output with some noise
        vad_output = [
            (0.0, 1.0, 0.85),
            (1.05, 1.3, 0.45),  # Below threshold, will be filtered
            (1.5, 3.0, 0.90),
        ]
        result = process_segments(vad_output, default_config, total_duration=5.0)
        # After filtering, only 2 segments pass threshold
        assert len(result) == 2
        assert all(isinstance(s, Segment) for s in result)

    def test_process_segments_with_default_config(self) -> None:
        """Should work with default config."""
        vad_output = [(0.0, 2.0, 0.80), (3.0, 5.0, 0.75)]
        result = process_segments(vad_output, VADConfig(), total_duration=10.0)
        assert len(result) == 2
        # Check padding applied (default 30ms = 0.03s)
        assert result[0].start_time == 0.0  # Clamped at 0
        assert abs(result[0].end_time - 2.03) < 0.001

    def test_process_segments_outputs_segment_models(self, default_config: VADConfig) -> None:
        """Should return Segment models."""
        vad_output = [(0.0, 1.0, 0.80)]
        result = process_segments(vad_output, default_config, total_duration=10.0)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Segment)
        assert result[0].start_time == 0.0
        assert result[0].end_time >= 1.0  # With padding
        assert result[0].confidence == 0.80
        assert result[0].text == ""

    def test_process_segments_empty_input(self, default_config: VADConfig) -> None:
        """Empty VAD output should return empty list."""
        result = process_segments([], default_config, total_duration=10.0)
        assert result == []

    def test_process_segments_merges_short(self) -> None:
        """Should merge short segments."""
        config = VADConfig(min_segment_duration=0.5, min_silence_duration_ms=200)
        # Two short segments with small gap
        vad_output = [
            (0.0, 0.2, 0.80),  # 0.2s < 0.5s min
            (0.25, 0.8, 0.70),  # Gap 0.05s < 0.2s
        ]
        result = process_segments(vad_output, config, total_duration=5.0)
        # Should merge into 1 segment
        assert len(result) == 1
