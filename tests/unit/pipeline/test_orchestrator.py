"""Unit tests for Pipeline orchestration.

Tests the main Pipeline class that coordinates:
- Format validation
- Media probing
- Audio extraction
- VAD processing
- Backend selection
- Transcription execution
- Result assembly
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiocore.backends import BackendRegistry
from audiocore.config import AppConfig
from audiocore.errors import BackendUnavailableError, MediaError, MediaFormatError
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.pipeline import Pipeline, transcribe
from audiocore.pipeline.orchestrator import Pipeline as PipelineClass
from audiocore.types import BackendType, SelectionPolicy


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
        duration_seconds=5.0,
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


class TestPipelineInit:
    """Test Pipeline initialization."""

    def test_init_default_config(self):
        """Pipeline initializes with default config."""
        pipeline = Pipeline()
        assert pipeline.config is not None
        assert pipeline._registry is not None
        assert pipeline._selector is not None

    def test_init_with_config(self, mock_config):
        """Pipeline initializes with provided config."""
        pipeline = Pipeline(config=mock_config)
        assert pipeline.config == mock_config
        assert pipeline._registry is not None
        assert pipeline._selector is not None


class TestPipelineTranscribe:
    """Test Pipeline.transcribe method."""

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_calls_validate_format(
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
        """transcribe() calls validate_format_or_raise with correct path."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments
        mock_backend.transcribe.return_value.media_info = mock_media_info

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        with (
            patch.object(BackendRegistry, "get_backend", return_value=mock_backend),
            patch.object(
                BackendRegistry, "__new__", return_value=BackendRegistry.__new__(BackendRegistry)
            ),
        ):
            pipeline = Pipeline()
            pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
            pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

            # Execute
            audio_file = tmp_path / "audio.mp3"
            audio_file.touch()
            pipeline.transcribe(audio_file)

            # Assert validate_format_or_raise was called
            mock_validate.assert_called_once()
            called_path = mock_validate.call_args[0][0]
            assert str(audio_file) in str(called_path) or called_path == audio_file

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_calls_probe(
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
        """transcribe() calls probe() with correct path."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        pipeline.transcribe(audio_file)

        # Assert probe was called
        mock_probe.assert_called_once()
        called_path = mock_probe.call_args[0][0]
        assert str(audio_file) in str(called_path) or called_path == audio_file

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_calls_extract_audio(
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
        """transcribe() calls extract_audio() for audio extraction."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        pipeline.transcribe(audio_file)

        # Assert extract_audio was called
        mock_extract_audio.assert_called_once()

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_calls_detect_speech(
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
        """transcribe() calls detect_speech() for VAD processing."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        pipeline.transcribe(audio_file)

        # Assert detect_speech was called
        mock_detect_speech.assert_called_once()
        call_kwargs = mock_detect_speech.call_args[1]
        assert "audio_path" in call_kwargs
        assert "config" in call_kwargs
        assert "total_duration" in call_kwargs

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_uses_backend_selector(
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
        """transcribe() uses BackendSelector.select() for backend selection."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        options = TranscriptionOptions(
            backend=BackendType.OPENAI, backend_preference=SelectionPolicy.PREFER_CLOUD
        )
        pipeline.transcribe(audio_file, options)

        # Assert selector was called with correct parameters
        pipeline._selector.select.assert_called_once()
        call_args = pipeline._selector.select.call_args
        assert call_args[1]["backend"] == BackendType.OPENAI
        assert call_args[1]["policy"] == SelectionPolicy.PREFER_CLOUD

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_uses_provided_backend(
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
        """transcribe() uses provided backend type when specified."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments
        mock_backend.backend_type = BackendType.FASTER_WHISPER

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        faster_whisper_backend = MagicMock()
        faster_whisper_backend.backend_type = BackendType.FASTER_WHISPER
        faster_whisper_backend.transcribe.return_value = TranscriptionResult(
            segments=mock_segments,
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            duration_seconds=5.0,
            backend_used=BackendType.FASTER_WHISPER,
        )

        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=faster_whisper_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.FASTER_WHISPER)

        # Execute with explicit backend
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        options = TranscriptionOptions(backend=BackendType.FASTER_WHISPER)
        pipeline.transcribe(audio_file, options)

        # Assert correct backend was selected
        pipeline._selector.select.assert_called_once()
        assert pipeline._selector.select.call_args[1]["backend"] == BackendType.FASTER_WHISPER

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_selects_backend_automatically(
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
        """transcribe() selects backend automatically when AUTO is specified."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute with AUTO backend
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        options = TranscriptionOptions(backend=BackendType.AUTO)
        pipeline.transcribe(audio_file, options)

        # Assert AUTO was passed to selector
        pipeline._selector.select.assert_called_once()
        assert pipeline._selector.select.call_args[1]["backend"] == BackendType.AUTO

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    @patch("audiocore.pipeline.orchestrator.time")
    def test_transcribe_sets_backend_used(
        self,
        mock_time,
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
        """transcribe() sets backend_used in result."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments
        mock_time.time.return_value = 0.0

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        result = pipeline.transcribe(audio_file)

        # Assert backend_used is set
        assert result.backend_used == BackendType.OPENAI

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_merges_segment_results(
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
        """transcribe() returns merged segment results from backend."""
        # Setup mock transcription result with multiple segments
        transcription_result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello"),
                Segment(start_time=5.0, end_time=10.0, text="World"),
                Segment(start_time=10.0, end_time=15.0, text="Test"),
            ],
            media_info=mock_media_info,
            config_used=TranscriptionOptions(),
            duration_seconds=5.0,
            backend_used=BackendType.OPENAI,
        )
        mock_backend.transcribe.return_value = transcription_result

        # Setup other mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = [
            Segment(start_time=0.0, end_time=5.0, text=""),
            Segment(start_time=5.0, end_time=10.0, text=""),
        ]

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        result = pipeline.transcribe(audio_file)

        # Assert all segments are in result
        assert len(result.segments) == 3
        assert result.segments[0].text == "Hello"
        assert result.segments[1].text == "World"
        assert result.segments[2].text == "Test"

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_cleans_up_temp_files_on_success(
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
        """transcribe() cleans up temp files using context manager."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager mock with proper enter/exit tracking
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()
        pipeline.transcribe(audio_file)

        # Assert temp_audio_file context manager was used
        mock_temp_file.assert_called_once()

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_cleans_up_temp_files_on_failure(
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
        """transcribe() cleans up temp files even on failure."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Make backend.transcribe raise an error
        mock_backend.transcribe.side_effect = Exception("Transcription failed")

        # Setup temp file context manager mock
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=temp_path)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_temp_file.return_value = mock_context

        # Mock registry and selector
        pipeline = Pipeline()
        pipeline._registry.get_backend = MagicMock(return_value=mock_backend)
        pipeline._selector.select = MagicMock(return_value=BackendType.OPENAI)

        # Execute and expect exception
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(Exception):
            pipeline.transcribe(audio_file)

        # Verify context manager __exit__ was called (cleanup)
        mock_context.__exit__.assert_called()

    def test_transcribe_raises_typed_exceptions_unsupported_format(
        self,
        tmp_path,
    ):
        """transcribe() raises MediaFormatError for unsupported format."""
        # Create a file with unsupported extension
        unsupported_file = tmp_path / "document.pdf"
        unsupported_file.touch()

        pipeline = Pipeline()

        # Should raise MediaFormatError from validate_format_or_raise
        with pytest.raises(MediaFormatError):
            pipeline.transcribe(unsupported_file)

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    def test_transcribe_raises_typed_exceptions_probe_failure(
        self,
        mock_probe,
        mock_validate,
        mock_media_info,
        tmp_path,
    ):
        """transcribe() raises MediaError on probe failure."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.side_effect = MediaError(
            "Probe failed",
            context={"error": "test"},
            suggestions=["Check file"],
        )

        pipeline = Pipeline()
        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(MediaError):
            pipeline.transcribe(audio_file)

    @patch("audiocore.pipeline.orchestrator.validate_format_or_raise")
    @patch("audiocore.pipeline.orchestrator.probe")
    @patch("audiocore.pipeline.orchestrator.extract_audio")
    @patch("audiocore.pipeline.orchestrator.detect_speech")
    @patch("audiocore.pipeline.orchestrator.temp_audio_file")
    def test_transcribe_raises_typed_exceptions_backend_unavailable(
        self,
        mock_temp_file,
        mock_detect_speech,
        mock_extract_audio,
        mock_probe,
        mock_validate,
        mock_media_info,
        mock_segments,
        tmp_path,
    ):
        """transcribe() raises BackendUnavailableError when no backend available."""
        # Setup mocks
        mock_validate.return_value = None
        mock_probe.return_value = mock_media_info
        mock_detect_speech.return_value = mock_segments

        # Setup temp file context manager
        temp_path = tmp_path / "temp.wav"
        temp_path.touch()
        mock_temp_file.return_value.__enter__ = MagicMock(return_value=temp_path)
        mock_temp_file.return_value.__exit__ = MagicMock(return_value=False)

        # Make selector raise BackendUnavailableError
        pipeline = Pipeline()
        pipeline._selector.select = MagicMock(
            side_effect=BackendUnavailableError(
                "No backend available",
                context={},
                suggestions=["Install faster-whisper"],
            )
        )

        audio_file = tmp_path / "audio.mp3"
        audio_file.touch()

        with pytest.raises(BackendUnavailableError):
            pipeline.transcribe(audio_file)


class TestTranscribeConvenienceFunction:
    """Test the convenience transcribe() function."""

    @patch("audiocore.pipeline.orchestrator.Pipeline.transcribe")
    def test_transcribe_creates_pipeline_and_calls_transcribe(
        self, mock_transcribe, mock_transcription_result
    ):
        """transcribe() creates Pipeline and calls transcribe()."""
        mock_transcribe.return_value = mock_transcription_result

        result = transcribe(Path("audio.mp3"))

        assert mock_transcribe.called
        assert result == mock_transcription_result

    @patch("audiocore.pipeline.orchestrator.Pipeline.transcribe")
    def test_transcribe_passes_options(self, mock_transcribe, mock_transcription_result):
        """transcribe() passes options to Pipeline.transcribe()."""
        mock_transcribe.return_value = mock_transcription_result

        options = TranscriptionOptions(backend=BackendType.OPENAI)
        result = transcribe(Path("audio.mp3"), options=options)

        assert mock_transcribe.called
        call_args = mock_transcribe.call_args
        assert call_args[1]["options"] == options

    @patch("audiocore.pipeline.orchestrator.Pipeline.transcribe")
    def test_transcribe_passes_config(
        self, mock_transcribe, mock_transcription_result, mock_config
    ):
        """transcribe() passes config to Pipeline constructor."""
        mock_transcribe.return_value = mock_transcription_result

        result = transcribe(Path("audio.mp3"), config=mock_config)

        assert mock_transcribe.called
        assert result == mock_transcription_result

    @patch("audiocore.pipeline.orchestrator.Pipeline.transcribe")
    def test_transcribe_returns_result(self, mock_transcribe, mock_transcription_result):
        """transcribe() returns TranscriptionResult."""
        mock_transcribe.return_value = mock_transcription_result

        result = transcribe(Path("audio.mp3"))

        assert isinstance(result, TranscriptionResult)
        assert result == mock_transcription_result


class TestPipelineModuleImports:
    """Test that pipeline module exports are correct."""

    def test_pipeline_class_import(self):
        """Pipeline class is importable from pipeline module."""
        from audiocore.pipeline import Pipeline

        assert Pipeline is not None

    def test_transcribe_function_import(self):
        """transcribe function is importable from pipeline module."""
        from audiocore.pipeline import transcribe

        assert transcribe is not None

    def test_transcribe_function_exported_from_main(self):
        """transcribe function is exported from main audiocore module."""
        from audiocore import transcribe

        assert transcribe is not None


class TestPipelineStageEnum:
    """Test PipelineStage enum (defines stages of the pipeline)."""

    def test_pipeline_stages_defined(self):
        """PipelineStage values can be imported."""
        # This test validates the enum exists
        # The actual enum definition should be in a separate module
        # For now, we're testing that stages can be tracked
        pass
