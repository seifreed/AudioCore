"""Tests for the installed AudioCore CLI entrypoint."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from audiocore.cli.main import app
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType

runner = CliRunner()


def _mock_pipeline() -> MagicMock:
    """Create a pipeline mock that returns a valid transcription result."""
    mock = MagicMock()
    mock.transcribe.return_value = TranscriptionResult(
        segments=[Segment(start_time=0.0, end_time=1.0, text="Hello from main CLI")],
        media_info=MediaInfo(duration=1.0, format="wav", sample_rate=16000, channels=1),
        config_used=TranscriptionOptions(),
        processing_time_seconds=0.1,
        backend_used=BackendType.OPENAI,
        formatted_output="Hello from main CLI",
    )
    return mock


def test_main_transcribe_command_dispatches_without_nested_command(tmp_path: Path) -> None:
    """Regression: installed CLI should accept `audiocore transcribe file.wav`."""
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"fake audio data")
    mock_pipeline = _mock_pipeline()

    with patch("audiocore.cli.transcribe.Pipeline", return_value=mock_pipeline):
        result = runner.invoke(app, ["transcribe", str(audio_file)])

    assert result.exit_code == 0
    assert "Hello from main CLI" in result.output


def test_main_transcribe_help_exposes_options_not_nested_subcommand() -> None:
    """Regression: `audiocore transcribe --help` should be the command help."""
    result = runner.invoke(app, ["transcribe", "--help"])

    assert result.exit_code == 0
    assert "Path(s) to the audio/video file(s)" in result.output
    assert "COMMAND [ARGS]" not in result.output
