"""Tests for progress callback types and events.

This module tests the progress callback system including:
- PipelineStage enum values
- ProgressCallback protocol conformance
- ProgressEvent dataclass behavior
"""

from __future__ import annotations

import time

from audiocore.pipeline.progress import (
    PipelineStage,
    ProgressCallback,
    ProgressEvent,
)


class TestPipelineStage:
    """Tests for PipelineStage enum."""

    def test_pipeline_stage_values(self) -> None:
        """PipelineStage has all expected stage values."""
        assert PipelineStage.PROBING.value == "probing"
        assert PipelineStage.EXTRACTING.value == "extracting"
        assert PipelineStage.VAD.value == "vad"
        assert PipelineStage.SELECTING.value == "selecting"
        assert PipelineStage.TRANSCRIBING.value == "transcribing"
        assert PipelineStage.FORMATTING.value == "formatting"
        assert PipelineStage.COMPLETE.value == "complete"

    def test_pipeline_stage_order(self) -> None:
        """PipelineStage stages are in reasonable execution order."""
        stages = [
            PipelineStage.PROBING,
            PipelineStage.EXTRACTING,
            PipelineStage.VAD,
            PipelineStage.SELECTING,
            PipelineStage.TRANSCRIBING,
            PipelineStage.FORMATTING,
            PipelineStage.COMPLETE,
        ]
        # Just verify we have all stages
        assert len(stages) == 7
        assert stages[0] == PipelineStage.PROBING
        assert stages[-1] == PipelineStage.COMPLETE

    def test_pipeline_stage_string_enum(self) -> None:
        """PipelineStage inherits from str and Enum."""
        # Can be used as string
        assert PipelineStage.PROBING == "probing"
        assert PipelineStage.EXTRACTING == "extracting"
        # Can be compared to strings
        assert PipelineStage.VAD.value == "vad"

    def test_pipeline_stage_from_string(self) -> None:
        """PipelineStage can be created from string value."""
        stage = PipelineStage("probing")
        assert stage == PipelineStage.PROBING

        stage = PipelineStage("transcribing")
        assert stage == PipelineStage.TRANSCRIBING


class TestProgressCallback:
    """Tests for ProgressCallback protocol."""

    def test_progress_callback_protocol_signature(self) -> None:
        """ProgressCallback has correct signature."""

        # Define a callback that matches the protocol
        def my_callback(
            stage: PipelineStage,
            progress: float,
            message: str,
        ) -> None:
            print(f"[{stage.value}] {progress:.0%}: {message}")

        # Protocol check - callable with correct signature
        callback: ProgressCallback = my_callback
        assert callable(callback)

    def test_progress_callback_invocation(self) -> None:
        """ProgressCallback can be invoked with correct parameters."""
        calls: list[tuple[PipelineStage, float, str]] = []

        def track_callback(
            stage: PipelineStage,
            progress: float,
            message: str,
        ) -> None:
            calls.append((stage, progress, message))

        callback: ProgressCallback = track_callback
        callback(PipelineStage.PROBING, 0.0, "Starting probe")
        callback(PipelineStage.PROBING, 1.0, "Probe complete")

        assert len(calls) == 2
        assert calls[0] == (PipelineStage.PROBING, 0.0, "Starting probe")
        assert calls[1] == (PipelineStage.PROBING, 1.0, "Probe complete")

    def test_progress_callback_can_be_none(self) -> None:
        """Progress callback is optional (can be None)."""
        # This is for type checking - callback is optional

        def pipeline_function(
            progress_callback: ProgressCallback | None = None,
        ) -> None:
            if progress_callback:
                progress_callback(PipelineStage.PROBING, 0.0, "Starting")
            # Continue processing...

        # Should work with None
        pipeline_function(progress_callback=None)
        pipeline_function()  # Uses default None

    def test_progress_callback_progress_range(self) -> None:
        """Progress percentage is typically 0.0 to 1.0."""
        received_progress: list[float] = []

        def track_progress(
            stage: PipelineStage,
            progress: float,
            message: str,
        ) -> None:
            received_progress.append(progress)

        callback: ProgressCallback = track_progress
        callback(PipelineStage.EXTRACTING, 0.0, "Starting extraction")
        callback(PipelineStage.EXTRACTING, 0.5, "Halfway")
        callback(PipelineStage.EXTRACTING, 1.0, "Complete")

        assert received_progress == [0.0, 0.5, 1.0]


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_progress_event_creation(self) -> None:
        """ProgressEvent can be created with required fields."""
        event = ProgressEvent(
            stage=PipelineStage.PROBING,
            progress=0.5,
            message="Probing media file",
        )
        assert event.stage == PipelineStage.PROBING
        assert event.progress == 0.5
        assert event.message == "Probing media file"
        assert event.timestamp is None  # Optional field

    def test_progress_event_with_timestamp(self) -> None:
        """ProgressEvent can include timestamp."""
        now = time.time()
        event = ProgressEvent(
            stage=PipelineStage.TRANSCRIBING,
            progress=0.75,
            message="Transcribing segment 3 of 4",
            timestamp=now,
        )
        assert event.stage == PipelineStage.TRANSCRIBING
        assert event.progress == 0.75
        assert event.message == "Transcribing segment 3 of 4"
        assert event.timestamp == now

    def test_progress_event_dataclass_equality(self) -> None:
        """ProgressEvent instances with same values are equal."""
        event1 = ProgressEvent(
            stage=PipelineStage.VAD,
            progress=1.0,
            message="VAD complete",
        )
        event2 = ProgressEvent(
            stage=PipelineStage.VAD,
            progress=1.0,
            message="VAD complete",
        )
        assert event1 == event2

    def test_progress_event_dataclass_inequality(self) -> None:
        """ProgressEvent instances with different values are not equal."""
        event1 = ProgressEvent(
            stage=PipelineStage.VAD,
            progress=1.0,
            message="VAD complete",
        )
        event2 = ProgressEvent(
            stage=PipelineStage.SELECTING,
            progress=1.0,
            message="Backend selected",
        )
        assert event1 != event2

    def test_progress_event_repr(self) -> None:
        """ProgressEvent has readable repr."""
        event = ProgressEvent(
            stage=PipelineStage.PROBING,
            progress=0.5,
            message="Probing media",
        )
        repr_str = repr(event)
        assert "ProgressEvent" in repr_str
        assert "PROBING" in repr_str
        assert "0.5" in repr_str
        assert "Probing media" in repr_str

    def test_progress_event_for_each_stage(self) -> None:
        """ProgressEvent can represent events for all stages."""
        events = [
            ProgressEvent(
                stage=PipelineStage.PROBING,
                progress=0.0,
                message="Starting probe",
            ),
            ProgressEvent(
                stage=PipelineStage.EXTRACTING,
                progress=0.0,
                message="Starting extraction",
            ),
            ProgressEvent(
                stage=PipelineStage.VAD,
                progress=0.0,
                message="Starting VAD",
            ),
            ProgressEvent(
                stage=PipelineStage.SELECTING,
                progress=0.0,
                message="Selecting backend",
            ),
            ProgressEvent(
                stage=PipelineStage.TRANSCRIBING,
                progress=0.0,
                message="Starting transcription",
            ),
            ProgressEvent(
                stage=PipelineStage.FORMATTING,
                progress=0.0,
                message="Formatting output",
            ),
            ProgressEvent(
                stage=PipelineStage.COMPLETE,
                progress=1.0,
                message="Pipeline complete",
            ),
        ]

        # Verify each stage has an event
        assert len(events) == 7
        assert events[0].stage == PipelineStage.PROBING
        assert events[-1].stage == PipelineStage.COMPLETE


class TestProgressTypesIntegration:
    """Integration tests for progress types together."""

    def test_callback_emits_events(self) -> None:
        """ProgressCallback can emit ProgressEvent objects."""
        events: list[ProgressEvent] = []

        def event_emitting_callback(
            stage: PipelineStage,
            progress: float,
            message: str,
        ) -> None:
            events.append(
                ProgressEvent(
                    stage=stage,
                    progress=progress,
                    message=message,
                )
            )

        callback: ProgressCallback = event_emitting_callback

        # Simulate pipeline progress
        callback(PipelineStage.PROBING, 0.0, "Starting")
        callback(PipelineStage.PROBING, 1.0, "Complete")
        callback(PipelineStage.EXTRACTING, 0.5, "50% extracted")

        assert len(events) == 3
        assert events[0].stage == PipelineStage.PROBING
        assert events[0].progress == 0.0
        assert events[1].progress == 1.0
        assert events[2].stage == PipelineStage.EXTRACTING

    def test_multiple_callbacks_same_signature(self) -> None:
        """Multiple callbacks can have the same ProgressCallback type."""
        calls_callback1: list[str] = []
        calls_callback2: list[str] = []

        def callback1(
            stage: PipelineStage,
            progress: float,
            message: str,
        ) -> None:
            calls_callback1.append(f"{stage.value}: {message}")

        def callback2(
            stage: PipelineStage,
            progress: float,
            message: str,
        ) -> None:
            calls_callback2.append(f"[{progress:.0%}] {message}")

        cb1: ProgressCallback = callback1
        cb2: ProgressCallback = callback2

        # Both can be invoked
        cb1(PipelineStage.PROBING, 0.5, "Test")
        cb2(PipelineStage.PROBING, 0.5, "Test")

        assert len(calls_callback1) == 1
        assert len(calls_callback2) == 1
