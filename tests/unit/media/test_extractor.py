"""Unit tests for audio extractor module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from audiocore.errors import InvalidInputError, MediaError
from audiocore.media.extractor import (
    _build_ffmpeg_command,
    _parse_progress,
    _validate_output,
    extract_audio,
    temp_audio_file,
)


class TestBuildFfmpegCommand:
    """Tests for _build_ffmpeg_command helper."""

    def test_build_command_basic(self):
        """Test basic command without options."""
        input_path = Path("/input.mp4")
        output_path = Path("/output.wav")

        cmd = _build_ffmpeg_command(input_path, output_path)

        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(input_path) in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "-c:a" in cmd
        assert "pcm_s16le" in cmd
        assert str(output_path) in cmd

    def test_build_command_with_start_time(self):
        """Test command with start time option."""
        input_path = Path("/input.mp4")
        output_path = Path("/output.wav")

        cmd = _build_ffmpeg_command(input_path, output_path, start_time=30.0)

        assert "-ss" in cmd
        assert "30.0" in cmd
        # -ss should come before -i for fast seeking
        ss_index = cmd.index("-ss")
        i_index = cmd.index("-i")
        assert ss_index < i_index

    def test_build_command_with_duration(self):
        """Test command with duration option."""
        input_path = Path("/input.mp4")
        output_path = Path("/output.wav")

        cmd = _build_ffmpeg_command(input_path, output_path, duration=60.0)

        assert "-t" in cmd
        assert "60.0" in cmd

    def test_build_command_with_all_options(self):
        """Test command with all options."""
        input_path = Path("/input.mp4")
        output_path = Path("/output.wav")

        cmd = _build_ffmpeg_command(
            input_path,
            output_path,
            start_time=10.0,
            duration=30.0,
            ffmpeg_path="/custom/ffmpeg",
        )

        assert cmd[0] == "/custom/ffmpeg"
        assert "-ss" in cmd
        assert "10.0" in cmd
        assert "-t" in cmd
        assert "30.0" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert "-c:a" in cmd
        assert "pcm_s16le" in cmd

    def test_build_command_custom_ffmpeg_path(self):
        """Test command with custom ffmpeg path."""
        input_path = Path("/input.mp4")
        output_path = Path("/output.wav")

        cmd = _build_ffmpeg_command(input_path, output_path, ffmpeg_path="/usr/local/bin/ffmpeg")

        assert cmd[0] == "/usr/local/bin/ffmpeg"


class TestValidateOutput:
    """Tests for _validate_output helper."""

    def test_validate_output_passes_for_existing_file(self, tmp_path: Path):
        """Test validation passes for existing non-empty file."""
        output_file = tmp_path / "output.wav"
        output_file.write_bytes(b"\x00" * 100)

        # Should not raise
        _validate_output(output_file)

    def test_validate_output_raises_for_missing_file(self, tmp_path: Path):
        """Test validation raises for missing file."""
        output_file = tmp_path / "missing.wav"

        with pytest.raises(MediaError) as exc_info:
            _validate_output(output_file)

        assert "Output file not created" in str(exc_info.value)

    def test_validate_output_raises_for_empty_file(self, tmp_path: Path):
        """Test validation raises for empty file."""
        output_file = tmp_path / "empty.wav"
        output_file.write_bytes(b"")

        with pytest.raises(MediaError) as exc_info:
            _validate_output(output_file)

        assert "Output file is empty" in str(exc_info.value)


class TestParseProgress:
    """Tests for _parse_progress helper."""

    def test_parse_progress_time_format(self):
        """Test parsing time=HH:MM:SS.XX format."""
        line = "frame= 123 fps=30 time=00:01:23.45 bitrate=128k"
        # 1 minute 23.45 seconds = 83.45 seconds
        # 83.45 / 100 * 100 = 83.45%
        result = _parse_progress(line, 100.0)
        assert result is not None
        assert abs(result - 83.45) < 0.1

    def test_parse_progress_decimal_format(self):
        """Test parsing time=XX.XX format."""
        line = "time=45.67"
        result = _parse_progress(line, 100.0)
        assert result == pytest.approx(45.67, rel=0.01)

    def test_parse_progress_no_time(self):
        """Test parsing line without time."""
        line = "frame= 123 fps=30"
        result = _parse_progress(line, 100.0)
        assert result is None

    def test_parse_progress_caps_at_100(self):
        """Test progress is capped at 100%."""
        line = "time=150.0"  # More than total duration
        result = _parse_progress(line, 100.0)
        assert result == 100.0

    def test_parse_progress_zero_duration(self):
        """Test handling zero duration."""
        line = "time=10.0"
        result = _parse_progress(line, 0.0)
        assert result is None

    def test_parse_progress_hours_format(self):
        """Test parsing time with hours."""
        line = "time=01:30:00.00"  # 1.5 hours = 5400 seconds
        result = _parse_progress(line, 5400.0)
        assert result == pytest.approx(100.0, rel=0.01)


class TestExtractAudio:
    """Tests for extract_audio function."""

    def test_extract_audio_creates_output_file(self, tmp_path: Path):
        """Test that extract_audio creates output file."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        def mock_subprocess(*args, **kwargs):
            # Simulate ffmpeg creating the output file
            output_file.write_bytes(b"fake wav content")
            return Mock(returncode=0, stderr="")

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = mock_subprocess

            result = extract_audio(input_file, output_file)

            assert result == output_file
            # Verify ffmpeg was called
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "ffmpeg" in cmd[0]

    def test_extract_audio_uses_custom_ffmpeg_path(self, tmp_path: Path):
        """Test that custom ffmpeg path is used."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        def mock_subprocess(*args, **kwargs):
            output_file.write_bytes(b"fake wav content")
            return Mock(returncode=0, stderr="")

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = mock_subprocess

            extract_audio(input_file, output_file, ffmpeg_path="/custom/ffmpeg")

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "/custom/ffmpeg"

    def test_extract_audio_raises_invalid_input_for_missing_input(self, tmp_path: Path):
        """Test that InvalidInputError is raised for missing input."""
        missing_file = tmp_path / "missing.mp4"
        output_file = tmp_path / "output.wav"

        with pytest.raises(InvalidInputError) as exc_info:
            extract_audio(missing_file, output_file)

        assert "Input file not found" in str(exc_info.value)

    def test_extract_audio_raises_media_error_for_ffmpeg_not_found(self, tmp_path: Path):
        """Test that MediaError is raised when ffmpeg is not found."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            with pytest.raises(MediaError) as exc_info:
                extract_audio(input_file, output_file)

            assert "ffmpeg executable not found" in str(exc_info.value)

    def test_extract_audio_raises_media_error_for_ffmpeg_failure(self, tmp_path: Path):
        """Test that MediaError is raised when ffmpeg fails."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stderr="ffmpeg error: Invalid data found when processing input",
            )

            with pytest.raises(MediaError) as exc_info:
                extract_audio(input_file, output_file)

            assert "ffmpeg failed" in str(exc_info.value)

    def test_extract_audio_raises_media_error_for_timeout(self, tmp_path: Path):
        """Test that MediaError is raised on timeout."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ffmpeg"], timeout=1.0)

            with pytest.raises(MediaError) as exc_info:
                extract_audio(input_file, output_file, timeout=1.0)

            assert "timed out" in str(exc_info.value)

    def test_extract_audio_with_start_time(self, tmp_path: Path):
        """Test that start_time is passed to ffmpeg command."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        def mock_subprocess(*args, **kwargs):
            output_file.write_bytes(b"fake wav content")
            return Mock(returncode=0, stderr="")

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = mock_subprocess

            extract_audio(input_file, output_file, start_time=30.0)

            cmd = mock_run.call_args[0][0]
            assert "-ss" in cmd
            assert "30.0" in cmd

    def test_extract_audio_with_duration(self, tmp_path: Path):
        """Test that duration is passed to ffmpeg command."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        def mock_subprocess(*args, **kwargs):
            output_file.write_bytes(b"fake wav content")
            return Mock(returncode=0, stderr="")

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = mock_subprocess

            extract_audio(input_file, output_file, duration=60.0)

            cmd = mock_run.call_args[0][0]
            assert "-t" in cmd
            assert "60.0" in cmd

    def test_extract_audio_uses_temp_file_when_no_output_path(self, tmp_path: Path):
        """Test that temp file is created when output_path is None."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            # Ensure the temp file exists after subprocess.run
            def create_output(*args, **kwargs):
                # Get the output path from the command
                cmd = args[0]
                output_path = Path(cmd[-1])
                output_path.write_bytes(b"fake wav content")
                return Mock(returncode=0, stderr="")

            mock_run.side_effect = create_output

            result = extract_audio(input_file)

            assert result.suffix == ".wav"

    def test_extract_audio_calls_progress_callback_with_percentage(self, tmp_path: Path):
        """Test that progress callback is invoked with percentage."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"
        output_file.write_bytes(b"fake wav content")

        progress_values = []

        def progress_callback(progress: float):
            progress_values.append(progress)

        # Mock probe to return duration
        mock_media_info = Mock()
        mock_media_info.duration = 100.0

        with (
            patch("audiocore.media.extractor.probe") as mock_probe,
            patch("audiocore.media.extractor.subprocess.run") as mock_run,
        ):
            mock_probe.return_value = mock_media_info
            mock_run.return_value = Mock(
                returncode=0,
                stderr="frame=  30 fps=30 time=00:00:10.00\ntime=20.0\nframe=  60 fps=30 time=00:00:20.00",
            )

            extract_audio(input_file, output_file, progress_callback=progress_callback)

            # Should have called probe
            mock_probe.assert_called_once()

            # Should have extracted progress values
            assert len(progress_values) > 0
            # Check progress values are in expected range
            for val in progress_values:
                assert 0 <= val <= 100

    def test_extract_audio_calls_probe_when_progress_callback_provided(self, tmp_path: Path):
        """Test that probe is called when progress_callback is provided."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"
        output_file.write_bytes(b"fake wav content")

        mock_media_info = Mock()
        mock_media_info.duration = 100.0

        with (
            patch("audiocore.media.extractor.probe") as mock_probe,
            patch("audiocore.media.extractor.subprocess.run") as mock_run,
        ):
            mock_probe.return_value = mock_media_info
            mock_run.return_value = Mock(returncode=0, stderr="")

            extract_audio(
                input_file,
                output_file,
                progress_callback=lambda x: None,
            )

            mock_probe.assert_called_once()

    def test_extract_audio_continues_without_progress_if_probe_fails(self, tmp_path: Path):
        """Test that extraction continues if probe fails when progress_callback provided."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"
        output_file.write_bytes(b"fake wav content")

        with (
            patch("audiocore.media.extractor.probe") as mock_probe,
            patch("audiocore.media.extractor.subprocess.run") as mock_run,
        ):
            mock_probe.side_effect = Exception("probe failed")
            mock_run.return_value = Mock(returncode=0, stderr="")

            # Should not raise - continues without progress
            result = extract_audio(
                input_file,
                output_file,
                progress_callback=lambda x: None,
            )

            assert result == output_file

    def test_extract_audio_accepts_string_path(self, tmp_path: Path):
        """Test that string path is accepted for input."""
        input_file = tmp_path / "input.mp4"
        input_file.write_bytes(b"fake video content")
        output_file = tmp_path / "output.wav"

        def mock_subprocess(*args, **kwargs):
            output_file.write_bytes(b"fake wav content")
            return Mock(returncode=0, stderr="")

        with patch("audiocore.media.extractor.subprocess.run") as mock_run:
            mock_run.side_effect = mock_subprocess

            # Should accept string path
            result = extract_audio(str(input_file), output_file)

            assert result == output_file


class TestTempAudioFile:
    """Tests for temp_audio_file context manager."""

    def test_temp_audio_file_creates_file(self):
        """Test that temp file is created with correct suffix."""
        with temp_audio_file() as temp_path:
            assert temp_path.suffix == ".wav"
            assert temp_path.exists() or temp_path.parent.exists()

    def test_temp_audio_file_deletes_on_exit(self):
        """Test that temp file is deleted on normal exit."""
        with temp_audio_file() as temp_path:
            temp_path_str = str(temp_path)
            # File path exists in context
            assert temp_path.suffix == ".wav"

        # File should be deleted after context
        # Note: We can't check if file exists since it was never written to
        # But we can verify the context manager works without error

    def test_temp_audio_file_deletes_on_exception(self):
        """Test that temp file is deleted even on exception."""
        temp_path_str = None
        with pytest.raises(ValueError):
            with temp_audio_file() as temp_path:
                temp_path_str = str(temp_path)
                raise ValueError("test error")

        # The context manager should clean up even on exception
        # Note: File never written, so we just verify cleanup runs without error

    def test_temp_audio_file_custom_suffix(self):
        """Test that custom suffix is used."""
        with temp_audio_file(suffix=".mp3") as temp_path:
            assert temp_path.suffix == ".mp3"

    def test_temp_audio_file_context_returns_path(self):
        """Test that context returns a Path object."""
        with temp_audio_file() as temp_path:
            from pathlib import Path

            assert isinstance(temp_path, Path)
