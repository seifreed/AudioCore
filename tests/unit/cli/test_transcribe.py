"""Unit tests for CLI transcribe command.

Tests verify:
- Command invocation with various options
- Output to file and stdout
- Error handling and exit codes
- Progress display
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer import BadParameter
from typer.testing import CliRunner

from audiocore.cli.transcribe import app
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

runner = CliRunner()


@pytest.fixture
def mock_pipeline() -> MagicMock:
    """Create a mock Pipeline instance."""
    mock = MagicMock()
    mock.transcribe.return_value = TranscriptionResult(
        segments=[
            Segment(start_time=0.0, end_time=5.0, text="Hello world"),
            Segment(start_time=5.0, end_time=10.0, text="This is a test"),
        ],
        media_info=MediaInfo(duration=10.0, format="wav", sample_rate=16000, channels=1),
        config_used=TranscriptionOptions(),
        processing_time_seconds=5.0,
        backend_used=BackendType.OPENAI,
        formatted_output="Hello world\nThis is a test",
    )
    return mock


@pytest.fixture
def audio_file(tmp_path: Path) -> Path:
    """Create a temporary audio file for testing."""
    audio_path = tmp_path / "test.wav"
    audio_path.write_bytes(b"fake audio data")
    return audio_path


class TestTranscribeCommand:
    """Test transcribe command functionality."""

    def test_transcribe_basic(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test basic transcription to stdout."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0
        assert "Hello world" in result.output

    def test_transcribe_to_file(
        self, audio_file: Path, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        """Test transcription to output file."""
        output_file = tmp_path / "output.txt"

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--output", str(output_file)])

        assert result.exit_code == 0
        assert "Transcription saved to" in result.output

    def test_transcribe_with_format(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with specific output format."""
        mock_pipeline.transcribe.return_value = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test segment")],
            media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
            config_used=TranscriptionOptions(output_format=OutputFormat.JSON),
            processing_time_seconds=2.0,
            backend_used=BackendType.OPENAI,
            formatted_output='{"segments": [{"text": "Test segment"}]}',
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--format", "json"])

        assert result.exit_code == 0

    def test_json_to_stdout_is_parseable(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Regression: JSON printed to stdout must be byte-exact and parseable.

        The progress bar previously rendered to stdout and rich markup/width
        wrapping mangled structured output, breaking `... --format json | jq`.
        """
        import json

        payload = '{"segments": [{"text": "Hello [bracketed] world", "start_time": 0.0}]}'
        mock_pipeline.transcribe.return_value = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello [bracketed] world")],
            media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
            config_used=TranscriptionOptions(output_format=OutputFormat.JSON),
            processing_time_seconds=2.0,
            backend_used=BackendType.OPENAI,
            formatted_output=payload,
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--format", "json"])

        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["segments"][0]["text"] == "Hello [bracketed] world"

    def test_stdout_preserves_literal_brackets(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """Regression: bracketed text (e.g. timestamps) is not eaten as rich markup."""
        mock_pipeline.transcribe.return_value = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="hi")],
            media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
            formatted_output="[00:00:00.000] hi",
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0
        assert "[00:00:00.000] hi" in result.output

    def test_transcribe_with_backend(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with specific backend."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--backend", "openai"])

        assert result.exit_code == 0

        # Verify options passed correctly
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert options.backend == BackendType.OPENAI

    def test_transcribe_with_language(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with language option."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--language", "en"])

        assert result.exit_code == 0

        # Verify language passed
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert options.language == "en"

    def test_transcribe_with_model(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with model size option."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--model", "small"])

        assert result.exit_code == 0

        # Verify model size passed
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert options.model_size == ModelSize.SMALL

    def test_transcribe_with_backend_preference(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """Test transcription with backend preference."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--prefer", "prefer_local"])

        assert result.exit_code == 0

        # Verify preference passed
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert options.backend_preference == SelectionPolicy.PREFER_LOCAL

    def test_transcribe_with_strict_vad_flag(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """Regression: documented --strict-vad flag should set transcription options."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--strict-vad"])

        assert result.exit_code == 0
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert options.strict_vad is True
        assert "strict_vad" in options.model_fields_set

    def test_transcribe_with_word_timestamps_flag(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """The --word-timestamps flag enables word_timestamps on the options."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--word-timestamps"])

        assert result.exit_code == 0
        options = mock_pipeline.transcribe.call_args[1]["options"]
        assert options.word_timestamps is True

    def test_transcribe_with_translate_flag(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """The --translate flag sets the task to TRANSLATE."""
        from audiocore.types import TranscriptionTask

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--translate"])

        assert result.exit_code == 0
        options = mock_pipeline.transcribe.call_args[1]["options"]
        assert options.task == TranscriptionTask.TRANSLATE

    def test_transcribe_uses_config_defaults_when_flags_omitted(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """Regression: omitted CLI flags should not overwrite loaded config values."""
        from audiocore.config import AppConfig

        config = AppConfig(
            backend=BackendType.OPENAI,
            model=ModelSize.SMALL,
            language="es",
            output_format=OutputFormat.JSON,
            backend_preference=SelectionPolicy.PREFER_CLOUD,
        )

        with (
            patch("audiocore.cli.transcribe.load_config", return_value=config),
            patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline),
        ):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert options.backend == BackendType.OPENAI
        assert options.model_size == ModelSize.SMALL
        assert options.language == "es"
        assert options.output_format == OutputFormat.JSON
        assert options.backend_preference == SelectionPolicy.PREFER_CLOUD

    def test_transcribe_omitted_model_does_not_mask_faster_whisper_config_model(
        self, audio_file: Path, mock_pipeline: MagicMock
    ) -> None:
        """Regression: omitted --model must not override nested faster-whisper model."""
        from audiocore.config import AppConfig
        from audiocore.config.faster_whisper_config import FasterWhisperConfig

        config = AppConfig(
            backend=BackendType.FASTER_WHISPER,
            faster_whisper=FasterWhisperConfig(model_size=ModelSize.TINY),
        )

        with (
            patch("audiocore.cli.transcribe.load_config", return_value=config),
            patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline),
        ):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        options = call_args[1]["options"]
        assert "model_size" not in options.model_fields_set

    def test_transcribe_file_not_found(self, mock_pipeline: MagicMock) -> None:
        """Test transcription with non-existent file."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, ["/nonexistent/audio.mp3"])

        # Typer handles file validation before command runs
        assert result.exit_code != 0

    def test_transcribe_invalid_backend(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with invalid backend type."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--backend", "invalid_backend"])

        assert result.exit_code != 0

    def test_transcribe_invalid_model(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with invalid model size."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--model", "huge"])

        assert result.exit_code != 0

    def test_transcribe_invalid_format(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test transcription with invalid output format."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--format", "invalid"])

        assert result.exit_code != 0


class TestTranscribeErrorHandling:
    """Test error handling in transcribe command."""

    def test_file_not_found_error(self, audio_file: Path) -> None:
        """Test FileNotFoundError handling."""
        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = FileNotFoundError("File not found")

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_permission_error(self, audio_file: Path) -> None:
        """Test PermissionError handling."""
        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = PermissionError("Permission denied")

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_config_error(self, audio_file: Path) -> None:
        """Test configuration error handling."""
        from audiocore.errors import ConfigurationError

        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = ConfigurationError(
            "Invalid configuration",
            context={},
            suggestions=["Fix the configuration"],
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 2

    def test_backend_unavailable_error(self, audio_file: Path) -> None:
        """Test BackendUnavailableError handling."""
        from audiocore.errors import BackendUnavailableError

        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = BackendUnavailableError(
            "Backend not available",
            context={},
            suggestions=["Install backend"],
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 4

    def test_output_error(self, audio_file: Path) -> None:
        """Test output error handling."""
        from audiocore.errors import MediaFormatError

        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = MediaFormatError(
            "Invalid format",
            context={},
            suggestions=["Use supported format"],
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code != 0

    def test_output_directory_error_returns_output_exit_code(
        self, audio_file: Path, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        """Regression: output path validation errors should use exit code 5."""
        output_dir = tmp_path / "existing-dir"
        output_dir.mkdir()

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--output", str(output_dir)])

        assert result.exit_code == 5
        assert "Output Error" in result.output

    def test_processing_error(self, audio_file: Path) -> None:
        """Test processing error handling."""
        from audiocore.errors import MediaError

        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = MediaError(
            "Processing failed",
            context={},
            suggestions=["Try again"],
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 3

    def test_backend_error_with_config_in_message(self, audio_file: Path) -> None:
        """Regression: BackendError with 'config' in message must not be misclassified.

        Previously, string-based classification checked "config" in str(e).lower(),
        so BackendUnavailableError("Backend configuration failed") was misclassified
        as exit_code=2 (config) instead of exit_code=4 (backend).
        Now uses isinstance checks for correct classification.
        """
        from audiocore.errors import BackendUnavailableError

        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = BackendUnavailableError(
            "Backend configuration failed",
            context={},
            suggestions=["Check backend setup"],
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 4

    def test_config_error_with_backend_in_message(self, audio_file: Path) -> None:
        """Regression: ConfigurationError with 'backend' in message stays exit_code=2."""
        from audiocore.errors import ConfigurationError

        mock_pipeline = MagicMock()
        mock_pipeline.transcribe.side_effect = ConfigurationError(
            "Invalid backend configuration",
            context={},
            suggestions=["Fix config"],
        )

        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 2


class TestTranscribeProgress:
    """Test progress display in transcribe command."""

    def test_progress_callback_called(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test that progress callback is passed to pipeline.transcribe()."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0

        # Verify progress_callback was passed
        call_args = mock_pipeline.transcribe.call_args
        assert call_args is not None
        assert "progress_callback" in call_args[1]
        assert call_args[1]["progress_callback"] is not None


class TestValidateInputFiles:
    """Regression tests for input file validation."""

    def test_nonexistent_file_flagged(self, tmp_path: Path) -> None:
        """Non-existent files should be flagged."""
        from audiocore.cli.transcribe import validate_input_files

        nonexistent = tmp_path / "does_not_exist.mp3"
        with pytest.raises(BadParameter):
            validate_input_files([nonexistent])

    def test_unreadable_file_flagged(self, tmp_path: Path) -> None:
        """Regression: files that exist but are not readable should be flagged.

        Previously the condition was `not file_path.exists() and file_path.exists()`
        which was always False, so unreadable files were silently accepted.
        """
        import os

        from audiocore.cli.transcribe import validate_input_files

        # Create a file and make it unreadable
        unreadable = tmp_path / "unreadable.mp3"
        unreadable.write_bytes(b"fake audio data")

        # Skip on platforms where chmod doesn't work (Windows)
        if os.name != "nt":
            unreadable.chmod(0o000)
            try:
                with pytest.raises(BadParameter):
                    validate_input_files([unreadable])
            finally:
                # Restore permissions for cleanup
                unreadable.chmod(0o644)

    def test_valid_file_accepted(self, tmp_path: Path) -> None:
        """Valid, readable files should be accepted."""
        from audiocore.cli.transcribe import validate_input_files

        valid_file = tmp_path / "valid.mp3"
        valid_file.write_bytes(b"fake audio data")
        result = validate_input_files([valid_file])
        assert result == [valid_file]


class TestTranscribeOptions:
    """Test option parsing for transcribe command."""

    def test_parse_backend_type_valid(self) -> None:
        """Test valid backend type parsing."""
        from audiocore.cli.transcribe import parse_backend_type

        assert parse_backend_type("openai") == BackendType.OPENAI
        assert parse_backend_type("OPENAI") == BackendType.OPENAI
        assert parse_backend_type("OpenAI") == BackendType.OPENAI
        assert parse_backend_type("faster_whisper") == BackendType.FASTER_WHISPER

    def test_parse_backend_type_invalid(self) -> None:
        """Test invalid backend type parsing."""
        import typer

        from audiocore.cli.transcribe import parse_backend_type

        with pytest.raises(typer.BadParameter):
            parse_backend_type("invalid")

    def test_parse_model_size_valid(self) -> None:
        """Test valid model size parsing."""
        from audiocore.cli.transcribe import parse_model_size

        assert parse_model_size("tiny") == ModelSize.TINY
        assert parse_model_size("TINY") == ModelSize.TINY
        assert parse_model_size("Tiny") == ModelSize.TINY
        assert parse_model_size("base") == ModelSize.BASE
        assert parse_model_size("small") == ModelSize.SMALL
        assert parse_model_size("medium") == ModelSize.MEDIUM
        assert parse_model_size("large") == ModelSize.LARGE

    def test_parse_model_size_invalid(self) -> None:
        """Test invalid model size parsing."""
        import typer

        from audiocore.cli.transcribe import parse_model_size

        with pytest.raises(typer.BadParameter):
            parse_model_size("huge")

    def test_parse_output_format_valid(self) -> None:
        """Test valid output format parsing."""
        from audiocore.cli.transcribe import parse_output_format

        assert parse_output_format("text") == OutputFormat.TEXT
        assert parse_output_format("TEXT") == OutputFormat.TEXT
        assert parse_output_format("json") == OutputFormat.JSON
        assert parse_output_format("srt") == OutputFormat.SRT
        assert parse_output_format("vtt") == OutputFormat.VTT

    def test_parse_output_format_invalid(self) -> None:
        """Test invalid output format parsing."""
        import typer

        from audiocore.cli.transcribe import parse_output_format

        with pytest.raises(typer.BadParameter):
            parse_output_format("invalid")

    def test_parse_selection_policy_valid(self) -> None:
        """Test valid selection policy parsing."""
        from audiocore.cli.transcribe import parse_selection_policy

        assert parse_selection_policy("auto") == SelectionPolicy.AUTO
        assert parse_selection_policy("prefer_local") == SelectionPolicy.PREFER_LOCAL
        assert parse_selection_policy("prefer_cloud") == SelectionPolicy.PREFER_CLOUD

    def test_parse_selection_policy_invalid(self) -> None:
        """Test invalid selection policy parsing."""
        import typer

        from audiocore.cli.transcribe import parse_selection_policy

        with pytest.raises(typer.BadParameter):
            parse_selection_policy("invalid")


class TestBatchTranscription:
    """Test batch transcription functionality."""

    def test_single_file_mode(self, audio_file: Path, mock_pipeline: MagicMock) -> None:
        """Test single file mode."""
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0
        assert "Hello world" in result.output

    def test_multiple_files_batch_mode(self, tmp_path: Path) -> None:
        """Test multiple files enables batch mode."""

        from audiocore.parallel.files import FileResult

        # Create multiple audio files
        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio data")
            files.append(audio_file)

        # Mock transcribe_files_concurrent
        mock_results = [
            FileResult(
                path=f,
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text=f"File {i}")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output=f"File {i}",
                ),
                error=None,
            )
            for i, f in enumerate(files)
        ]

        async def mock_transcribe_concurrent(*args, **kwargs):
            return mock_results

        with patch(
            "audiocore.cli.transcribe.transcribe_files_concurrent",
            side_effect=mock_transcribe_concurrent,
        ):
            result = runner.invoke(app, [str(f) for f in files])

        assert result.exit_code == 0
        assert "3 file(s)" in result.output

    def test_max_workers_option(self, tmp_path: Path) -> None:
        """Test --max-workers flag limits concurrency."""
        from audiocore.parallel.files import FileResult

        files = []
        for i in range(2):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio data")
            files.append(audio_file)

        mock_results = [
            FileResult(
                path=f,
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output="test",
                ),
                error=None,
            )
            for f in files
        ]

        captured_kwargs = {}

        async def mock_transcribe_concurrent(*args, **kwargs):
            captured_kwargs["max_workers"] = kwargs.get("max_workers", 4)
            return mock_results

        with patch(
            "audiocore.cli.transcribe.transcribe_files_concurrent",
            side_effect=mock_transcribe_concurrent,
        ):
            result = runner.invoke(app, [str(f) for f in files] + ["--max-workers", "2"])

        assert result.exit_code == 0
        assert captured_kwargs.get("max_workers") == 2

    def test_batch_mode_passes_loaded_config_to_workers(self, tmp_path: Path) -> None:
        """Regression: CLI batch mode must keep the config loaded by the command."""
        from audiocore.config import AppConfig
        from audiocore.parallel.files import FileResult

        files = []
        for i in range(2):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio data")
            files.append(audio_file)

        mock_results = [
            FileResult(
                path=f,
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output="test",
                ),
                error=None,
            )
            for f in files
        ]
        config = AppConfig()
        captured_kwargs = {}

        async def mock_transcribe_concurrent(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_results

        with (
            patch("audiocore.cli.transcribe.load_config", return_value=config),
            patch(
                "audiocore.cli.transcribe.transcribe_files_concurrent",
                side_effect=mock_transcribe_concurrent,
            ),
        ):
            result = runner.invoke(app, [str(f) for f in files])

        assert result.exit_code == 0
        assert captured_kwargs["config"] is config

    def test_batch_mode_with_output_dir(self, tmp_path: Path) -> None:
        """Test batch mode with output directory."""
        from audiocore.parallel.files import FileResult

        files = []
        for i in range(2):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio data")
            files.append(audio_file)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_results = [
            FileResult(
                path=f,
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output="test",
                ),
                error=None,
            )
            for f in files
        ]

        async def mock_transcribe_concurrent(*args, **kwargs):
            return mock_results

        with patch(
            "audiocore.cli.transcribe.transcribe_files_concurrent",
            side_effect=mock_transcribe_concurrent,
        ):
            result = runner.invoke(app, [str(f) for f in files] + ["--output-dir", str(output_dir)])

        assert result.exit_code == 0

    def test_batch_mode_exit_code_on_failure(self, tmp_path: Path) -> None:
        """Test exit code 1 when any file fails in batch mode."""
        from audiocore.parallel.files import FileResult

        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio data")
            files.append(audio_file)

        # One file fails
        mock_results = [
            FileResult(
                path=files[0],
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output="test",
                ),
                error=None,
            ),
            FileResult(
                path=files[1],
                success=False,
                result=None,
                error="Transcription failed",
            ),
            FileResult(
                path=files[2],
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output="test",
                ),
                error=None,
            ),
        ]

        async def mock_transcribe_concurrent(*args, **kwargs):
            return mock_results

        with patch(
            "audiocore.cli.transcribe.transcribe_files_concurrent",
            side_effect=mock_transcribe_concurrent,
        ):
            result = runner.invoke(app, [str(f) for f in files])

        assert result.exit_code == 1
        assert "failed" in result.output.lower()

    def test_batch_mode_all_success(self, tmp_path: Path) -> None:
        """Test exit code 0 when all files succeed in batch mode."""
        from audiocore.parallel.files import FileResult

        files = []
        for i in range(2):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio data")
            files.append(audio_file)

        mock_results = [
            FileResult(
                path=f,
                success=True,
                result=TranscriptionResult(
                    segments=[Segment(start_time=0.0, end_time=5.0, text="test")],
                    media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
                    config_used=TranscriptionOptions(),
                    processing_time_seconds=2.0,
                    backend_used=BackendType.OPENAI,
                    formatted_output="test",
                ),
                error=None,
            )
            for f in files
        ]

        async def mock_transcribe_concurrent(*args, **kwargs):
            return mock_results

        with patch(
            "audiocore.cli.transcribe.transcribe_files_concurrent",
            side_effect=mock_transcribe_concurrent,
        ):
            result = runner.invoke(app, [str(f) for f in files])

        assert result.exit_code == 0
        assert "successfully" in result.output.lower()


class TestTranscribeCoverageGaps:
    """Cover remaining branches in the transcribe CLI module."""

    def test_validate_input_files_rejects_directory(self, tmp_path: Path) -> None:
        from audiocore.cli.transcribe import validate_input_files

        with pytest.raises(BadParameter, match="is not a file"):
            validate_input_files([tmp_path])

    def test_print_result_falls_back_to_segments_without_formatted_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from rich.console import Console

        from audiocore.cli.transcribe import _print_transcription_result

        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=1.5, text="raw line")],
            media_info=MediaInfo(duration=1.5, format="wav", sample_rate=16000, channels=1),
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.1,
            backend_used=BackendType.OPENAI,
            formatted_output="",
        )
        _print_transcription_result(Console(), result)

        captured = capsys.readouterr()
        assert "raw line" in captured.out
        assert "0.000 - 1.500" in captured.out

    def test_config_error_exits_with_code_2(self, audio_file: Path) -> None:
        from audiocore.errors import ConfigurationError

        with patch(
            "audiocore.cli.transcribe.load_config",
            side_effect=ConfigurationError("bad config"),
        ):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 2
        assert "Configuration Error" in result.output

    def test_single_file_with_output_dir_generates_filename(
        self, audio_file: Path, mock_pipeline: MagicMock, tmp_path: Path
    ) -> None:
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
            result = runner.invoke(app, [str(audio_file), "--output-dir", str(out_dir)])

        assert result.exit_code == 0
        assert (out_dir / "test.text").exists()

    def test_progress_callback_is_driven_during_single_file(
        self, audio_file: Path, tmp_path: Path
    ) -> None:
        from audiocore.pipeline.progress import PipelineStage

        result_obj = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=1.0, text="hi")],
            media_info=MediaInfo(duration=1.0, format="wav", sample_rate=16000, channels=1),
            config_used=TranscriptionOptions(),
            processing_time_seconds=0.1,
            backend_used=BackendType.OPENAI,
            formatted_output="hi",
        )

        pipeline = MagicMock()

        def transcribe_with_progress(path, options, progress_callback):
            progress_callback(PipelineStage.PROBING, 0.5, "halfway")
            return result_obj

        pipeline.transcribe.side_effect = transcribe_with_progress

        with patch("audiocore.cli.transcribe.Pipeline", return_value=pipeline):
            result = runner.invoke(app, [str(audio_file)])

        assert result.exit_code == 0
        pipeline.transcribe.assert_called_once()

    def test_batch_audiocore_error_maps_to_exit_code(self, tmp_path: Path) -> None:
        from audiocore.errors import MediaError

        files = []
        for i in range(2):
            f = tmp_path / f"clip{i}.wav"
            f.write_bytes(b"fake audio")
            files.append(str(f))

        with patch(
            "audiocore.cli.transcribe.transcribe_files_concurrent",
            side_effect=MediaError("batch boom"),
        ):
            result = runner.invoke(app, [*files])

        assert result.exit_code != 0
