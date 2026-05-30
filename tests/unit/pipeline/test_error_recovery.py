"""Unit tests for Pipeline error recovery and cleanup.

Tests error handling, partial result preservation, and temp file cleanup:
- Cleanup on failure at each pipeline stage
- VAD fallback to whole-file transcription
- Partial result preservation
- User-friendly error messages
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from audiocore.config import AppConfig
from audiocore.errors import (
    MediaError,
    VADError,
)
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.pipeline import Pipeline
from audiocore.pipeline.cancellation import CancellationToken
from audiocore.pipeline.errors import (
    PartialResultError,
    PipelineCancelledError,
    PipelineStageError,
)
from audiocore.pipeline.progress import PipelineStage
from audiocore.types import BackendType


@pytest.fixture
def mock_media_info():
    """Create mock MediaInfo for testing."""
    return MediaInfo(
        duration=60.0,
        format="mp3",
        codec="mp3",
        sample_rate=44100,
        channels=2,
    )


@pytest.fixture
def mock_segments():
    """Create mock segments for testing."""
    return [
        Segment(start_time=0.0, end_time=5.0, text=""),
        Segment(start_time=5.0, end_time=10.0, text=""),
    ]


@pytest.fixture
def mock_transcription_result(mock_media_info):
    """Create mock TranscriptionResult for testing."""
    return TranscriptionResult(
        segments=[
            Segment(start_time=0.0, end_time=5.0, text="Hello world"),
            Segment(start_time=5.0, end_time=10.0, text="This is a test"),
        ],
        media_info=mock_media_info,
        config_used=TranscriptionOptions(),
        processing_time_seconds=5.0,
        backend_used=BackendType.OPENAI,
    )


@pytest.fixture
def mock_backend(mock_transcription_result):
    """Create mock transcription backend."""
    backend = MagicMock()
    backend.backend_type = BackendType.OPENAI
    backend.transcribe.return_value = mock_transcription_result
    backend.is_available.return_value = True
    backend.get_name.return_value = "Mock Backend"
    return backend


@pytest.fixture
def mock_config():
    """Create mock AppConfig for testing."""
    config = MagicMock(spec=AppConfig)
    config.vad = MagicMock()
    return config


class TestCleanupOnProbeFailure:
    """Test cleanup behavior when probe stage fails."""

    def test_cleanup_on_probe_failure_no_temp_files(
        self, tmp_path, mock_media_info, mock_segments, mock_backend
    ):
        """Probe failure doesn't create temp files, so no cleanup needed."""
        # Create a file that would pass format validation
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        # Mock probe to raise error
        with patch("audiocore.pipeline.orchestrator.probe") as mock_probe:
            mock_probe.side_effect = MediaError(
                "Probe failed",
                context={"file": str(audio_file)},
                suggestions=["Check file integrity"],
            )

            pipeline = Pipeline()
            pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
            pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

            with pytest.raises(PipelineStageError) as exc_info:
                pipeline.transcribe(audio_file)

            # Verify it's wrapped in PipelineStageError at PROBING stage
            assert exc_info.value.stage == PipelineStage.PROBING
            assert exc_info.value.original_error is not None
            assert isinstance(exc_info.value.original_error, MediaError)

    def test_probe_failure_preserves_error_context(self, tmp_path, mock_media_info):
        """Probe failure preserves error context and suggestions."""
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        original_error = MediaError(
            "ffprobe not found",
            context={"file": str(audio_file), "error": "ENOENT"},
            suggestions=["Install ffmpeg"],
        )

        with patch("audiocore.pipeline.orchestrator.probe") as mock_probe:
            mock_probe.side_effect = original_error

            pipeline = Pipeline()

            with pytest.raises(PipelineStageError) as exc_info:
                pipeline.transcribe(audio_file)

            # Verify context is preserved
            assert exc_info.value.context is not None
            assert "stage" in exc_info.value.context
            # Error suggestions should include stage-specific ones
            assert len(exc_info.value.suggestions) > 0


class TestCleanupOnExtractionFailure:
    """Test cleanup behavior when extraction stage fails."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_cleanup_on_extraction_failure(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        mock_segments,
        tmp_path,
    ):
        """Extraction failure cleans up temp files."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Mock extraction to fail
        mock_extract_audio.side_effect = MediaError(
            "Extraction failed",
            context={"input": str(tmp_path / "audio.mp3")},
            suggestions=["Check codec support"],
        )

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(PipelineStageError) as exc_info:
            pipeline.transcribe(audio_file)

        # Verify it's wrapped in PipelineStageError at EXTRACTING stage
        assert exc_info.value.stage == PipelineStage.EXTRACTING
        assert exc_info.value.original_error is not None
        assert isinstance(exc_info.value.original_error, MediaError)

        # Verify context manager cleanup was called
        mock_context.__exit__.assert_called()


class TestCleanupOnVADFailure:
    """Test cleanup behavior when VAD stage fails."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_vad_failure_falls_back_to_whole_file(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        mock_segments,
        tmp_path,
        caplog,
    ):
        """VAD failure logs warning and falls back to whole-file transcription."""
        caplog.set_level(logging.WARNING)

        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.side_effect = VADError(
            "VAD model failed",
            context={"model": "silero_vad"},
            suggestions=["Try whole-file transcription"],
        )

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        # Should NOT raise - falls back to whole-file transcription
        result = pipeline.transcribe(audio_file)

        # Verify VAD fallback warning was logged
        assert "VAD" in caplog.text
        assert "falling back" in caplog.text.lower() or "fallback" in caplog.text.lower()

        # Verify transcription completed (backend called with empty segments)
        assert result is not None

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_vad_failure_cleanup_temp_files(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        tmp_path,
    ):
        """VAD failure with subsequent backend failure cleans up temp files."""
        # Setup mocks - VAD fails, then backend fails
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.side_effect = VADError("VAD failed")

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Create mock result for fallback path
        mock_result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=60.0, text="Whole file transcription"),
            ],
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)
        mock_backend.transcribe.return_value = mock_result

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        # Falls back and succeeds
        result = pipeline.transcribe(audio_file)

        assert result is not None
        # Context manager cleanup was called
        mock_context.__exit__.assert_called()


class TestCleanupOnBackendFailure:
    """Test cleanup behavior when backend stage fails."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_backend_failure_wraps_in_pipeline_stage_error(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        mock_segments,
        tmp_path,
    ):
        """Backend failure is wrapped in PipelineStageError."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Mock backend to fail
        mock_backend.transcribe.side_effect = Exception("API timeout")

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(PipelineStageError) as exc_info:
            pipeline.transcribe(audio_file)

        # Verify error wrapping
        assert exc_info.value.stage == PipelineStage.TRANSCRIBING
        assert exc_info.value.original_error is not None
        assert "timeout" in str(exc_info.value.original_error).lower()

        # Context manager cleanup was called
        mock_context.__exit__.assert_called()

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_backend_failure_cleanup_temp_files(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        mock_segments,
        tmp_path,
    ):
        """Backend failure cleans up temp files."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Make backend fail
        mock_backend.transcribe.side_effect = Exception("Backend error")

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(PipelineStageError):
            pipeline.transcribe(audio_file)

        # Context manager __exit__ was called (cleanup)
        mock_context.__exit__.assert_called()


class TestCleanupOnCancellation:
    """Test cleanup behavior when pipeline is cancelled."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_cancellation_cleanup_temp_files(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        mock_segments,
        tmp_path,
    ):
        """Cancellation cleans up temp files when cancellation happens during processing."""
        from audiocore.pipeline.cancellation import CancelledError

        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Create token - cancel during VAD (after temp file creation)
        token = CancellationToken()

        def cancel_during_vad(*args, **kwargs):
            token.cancel()
            raise CancelledError()

        mock_detect_speech.side_effect = cancel_during_vad

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(CancelledError):
            pipeline.transcribe(audio_file, cancellation_token=token)

        # Context manager cleanup was called (temp files cleaned up)
        mock_temp_file.assert_called_once()
        mock_context.__exit__.assert_called()

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_cancellation_after_extraction_cleanup(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        tmp_path,
    ):
        """Cancellation after extraction cleans up temp files."""
        from audiocore.pipeline.cancellation import CancelledError

        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Create token
        token = CancellationToken()

        # Cancel during detect_speech
        def cancel_during_vad(*args, **kwargs):
            token.cancel()
            # VAD fails, triggers fallback - but cancellation should propagate
            raise CancelledError()

        mock_detect_speech.side_effect = cancel_during_vad

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(CancelledError):
            pipeline.transcribe(audio_file, cancellation_token=token)

        # Context manager cleanup was called
        mock_context.__exit__.assert_called()


class TestPartialResultPreservation:
    """Test partial result preservation on failure."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_vad_failure_returns_whole_file_result(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        tmp_path,
    ):
        """VAD failure with whole-file fallback returns successful result."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info

        # VAD fails, fallback to whole file
        mock_detect_speech.side_effect = VADError("VAD model error")

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Mock backend result for whole-file transcription
        whole_file_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=60.0, text="Whole file text")],
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )
        mock_backend.transcribe.return_value = whole_file_result

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        # Should succeed with whole-file fallback
        result = pipeline.transcribe(audio_file)

        assert result is not None
        assert len(result.segments) == 1
        assert result.segments[0].text == "Whole file text"

    def test_transcription_result_has_failed_segments_field(self, mock_media_info, mock_segments):
        """TranscriptionResult supports failed_segments field."""
        # Create result with failed_segments in constructor
        result = TranscriptionResult(
            segments=mock_segments,
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
            failed_segments=[{"start_time": 10.0, "end_time": 15.0, "error": "Backend timeout"}],
        )

        # Should have the failed segments
        assert result.failed_segments is not None
        assert len(result.failed_segments) == 1
        assert result.failed_segments[0].error == "Backend timeout"

        # Default should be empty list when not provided
        result2 = TranscriptionResult(
            segments=mock_segments,
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )
        assert result2.failed_segments == []


class TestUserFriendlyErrorMessages:
    """Test user-friendly error messages with context."""

    def test_pipeline_stage_error_includes_stage(self, mock_media_info):
        """PipelineStageError includes stage information."""
        error = PipelineStageError(
            "Transcription failed",
            stage=PipelineStage.TRANSCRIBING,
            context={"backend": "OpenAI"},
            original_error=Exception("API timeout"),
        )

        assert error.stage == PipelineStage.TRANSCRIBING
        assert "stage" in error.context
        assert error.context["stage"] == "transcribing"
        assert error.original_error is not None

    def test_pipeline_stage_error_has_suggestions(self, mock_media_info):
        """PipelineStageError provides stage-specific suggestions."""
        error = PipelineStageError(
            "Transcription failed",
            stage=PipelineStage.TRANSCRIBING,
        )

        # Should have stage-specific suggestions
        assert len(error.suggestions) > 0
        # TRANSCRIBING suggestions should mention backend/API
        suggestions_text = " ".join(error.suggestions).lower()
        assert "backend" in suggestions_text or "api" in suggestions_text

    def test_pipeline_stage_error_wraps_original(self, mock_media_info):
        """PipelineStageError preserves original error."""
        original = Exception("Connection refused")
        error = PipelineStageError(
            "Backend failed",
            stage=PipelineStage.SELECTING,
            original_error=original,
        )

        assert error.original_error == original
        assert error.original_error.__cause__ is None  # Not chained with 'from'

        # Can access original error for debugging
        assert str(error.original_error) == "Connection refused"

    def test_format_error_output(self, mock_media_info):
        """format_error() provides readable output."""
        error = PipelineStageError(
            "Failed to extract audio",
            stage=PipelineStage.EXTRACTING,
            context={"file": "audio.mp3"},
            suggestions=["Check ffmpeg installation", "Try different format"],
        )

        formatted = error.format_error()
        assert "[AUD-502]" in formatted
        assert "Failed to extract audio" in formatted
        assert "file" in formatted.lower()
        assert "Check ffmpeg" in formatted

    def test_pipeline_error_inherits_from_audiocore_error(self):
        """PipelineError inherits from AudioCoreError."""
        from audiocore.errors.base import AudioCoreError

        error = PipelineStageError("Test", stage=PipelineStage.PROBING)
        assert isinstance(error, AudioCoreError)

    def test_partial_result_error_preserves_result(self, mock_media_info, mock_segments):
        """PartialResultError can preserve partial TranscriptionResult."""
        partial_result = TranscriptionResult(
            segments=mock_segments,
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        error = PartialResultError(
            "Partial transcription failed",
            partial_result=partial_result,
            failed_segments=[{"start_time": 10.0, "end_time": 15.0, "error": "timeout"}],
        )

        assert error.partial_result == partial_result
        assert len(error.failed_segments) == 1
        assert error.failed_segments[0]["error"] == "timeout"

    def test_partial_result_error_context_includes_counts(self):
        """PartialResultError context includes segment counts."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
            media_info=MediaInfo(duration=10.0, format="mp3"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )

        error = PartialResultError(
            "Some segments failed",
            partial_result=result,
            failed_segments=[{"start_time": 5.0, "end_time": 10.0}],
        )

        assert "segments_completed" in error.context
        assert error.context["segments_completed"] == 1
        assert "segments_failed" in error.context
        assert error.context["segments_failed"] == 1


class TestPipelineExceptionsIntegration:
    """Test integration of pipeline exceptions with error hierarchy."""

    def test_pipeline_errors_importable_from_pipeline_module(self):
        """Pipeline errors can be imported from pipeline module."""
        from audiocore.pipeline import (
            PartialResultError,
            PipelineCancelledError,
            PipelineError,
            PipelineStageError,
        )

        assert PipelineError is not None
        assert PipelineStageError is not None
        assert PipelineCancelledError is not None
        assert PartialResultError is not None

    def test_pipeline_errors_importable_from_errors_module(self):
        """Pipeline errors can be imported from errors module."""
        from audiocore.errors import (
            PartialResultError,
            PipelineCancelledError,
            PipelineError,
            PipelineStageError,
        )

        assert PipelineError is not None
        assert PipelineStageError is not None
        assert PipelineCancelledError is not None
        assert PartialResultError is not None

    def test_pipeline_stage_error_error_codes(self):
        """PipelineStageError has correct error codes (AUD-50X)."""
        # PipelineError base - AUD-501
        from audiocore.pipeline.errors import PipelineError

        assert PipelineError.error_code == "AUD-501"

        # PipelineStageError - AUD-502
        assert PipelineStageError.error_code == "AUD-502"

        # PipelineCancelledError - AUD-503
        assert PipelineCancelledError.error_code == "AUD-503"

        # PartialResultError - AUD-504
        assert PartialResultError.error_code == "AUD-504"

    def test_exception_chaining_preserved(self):
        """Exception chaining is preserved through PipelineStageError."""
        original = MediaError("Original error")

        # Create PipelineStageError with 'from' to chain
        try:
            try:
                raise original
            except MediaError as e:
                raise PipelineStageError(
                    "Wrapped error",
                    stage=PipelineStage.PROBING,
                    original_error=e,
                ) from e
        except PipelineStageError as wrapped:
            # __cause__ should be set
            assert wrapped.__cause__ is original
            # original_error should also be set
            assert wrapped.original_error is original


class TestFormattingErrorNonFatal:
    """Test that formatting errors are non-fatal."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    @patch("audiocore.pipeline.orchestrator.format_text")
    def test_formatting_error_returns_none(
        self,
        mock_format_text,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_backend,
        mock_media_info,
        mock_segments,
        tmp_path,
        caplog,
    ):
        """Formatting failure logs warning but doesn't fail pipeline."""
        caplog.set_level(logging.WARNING)

        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Mock format to fail
        mock_format_text.side_effect = Exception("Formatter error")

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        # Should complete successfully
        result = pipeline.transcribe(audio_file)

        # Result should have segments but formatted_output should be None
        assert result is not None
        assert result.formatted_output is None

        # Warning should be logged
        assert "Failed to format output" in caplog.text


class TestPipelineErrorConstructorBranches:
    """Cover the constructor branches of the pipeline exception hierarchy."""

    def test_pipeline_error_default_suggestions(self):
        from audiocore.pipeline.errors import PipelineError

        error = PipelineError("boom")
        assert any("input file" in s.lower() for s in error.suggestions)

    def test_pipeline_error_stage_with_no_context_creates_context(self):
        from audiocore.pipeline.errors import PipelineError

        error = PipelineError("boom", stage=PipelineStage.VAD)
        assert error.context["stage"] == "vad"

    def test_cancelled_error_defaults(self):
        error = PipelineCancelledError()
        assert "Pipeline execution was cancelled" in str(error)
        assert any("Cancelling is intentional" in s for s in error.suggestions)
        assert "stage" not in error.context

    def test_cancelled_error_with_stage_context_and_suggestions(self):
        error = PipelineCancelledError(
            "stopped",
            stage=PipelineStage.TRANSCRIBING,
            context={"reason": "user"},
            suggestions=["bespoke"],
        )
        assert error.context["stage"] == "transcribing"
        assert error.context["reason"] == "user"
        assert error.suggestions == ["bespoke"]

    def test_partial_result_error_no_result_with_context_and_suggestions(self):
        error = PartialResultError(
            "partial",
            partial_result=None,
            failed_segments=None,
            context={"phase": "x"},
            suggestions=["only-this"],
        )
        assert error.context["phase"] == "x"
        assert "segments_completed" not in error.context
        assert "segments_failed" not in error.context
        assert error.suggestions == ["only-this"]
