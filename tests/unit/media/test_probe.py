"""Tests for probe() function in media module."""

import json
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

import pytest

from audiocore.errors import InvalidInputError, MediaError
from audiocore.media.probe import (
    _parse_duration,
    _validate_audio_stream,
    _validate_file_exists,
    probe,
)
from audiocore.models import MediaInfo


class TestValidateFileExists:
    """Tests for _validate_file_exists helper."""

    def test_validate_file_exists_passes_for_existing_file(self, tmp_path: Path) -> None:
        """Should pass when file exists."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("test content")

        # Should not raise
        _validate_file_exists(test_file)

    def test_validate_file_exists_raises_for_missing_file(self, tmp_path: Path) -> None:
        """Should raise InvalidInputError for missing file."""
        missing_file = tmp_path / "nonexistent.mp3"

        with pytest.raises(InvalidInputError) as exc_info:
            _validate_file_exists(missing_file)

        assert exc_info.value.error_code == "AUD-002"
        assert "File not found" in str(exc_info.value.message)
        assert str(missing_file) in str(exc_info.value.message)

    def test_validate_file_exists_includes_context(self, tmp_path: Path) -> None:
        """Should include file path in context."""
        missing_file = tmp_path / "missing.mp3"

        with pytest.raises(InvalidInputError) as exc_info:
            _validate_file_exists(missing_file)

        assert exc_info.value.context is not None
        assert "file_path" in exc_info.value.context
        assert exc_info.value.context["file_path"] == str(missing_file)

    def test_validate_file_exists_raises_for_directory(self, tmp_path: Path) -> None:
        """Directories are invalid media inputs even when the path exists."""
        media_dir = tmp_path / "audio.mp3"
        media_dir.mkdir()

        with pytest.raises(InvalidInputError) as exc_info:
            _validate_file_exists(media_dir)

        assert "not a file" in str(exc_info.value)
        assert exc_info.value.context["file_path"] == str(media_dir)


class TestValidateAudioStream:
    """Tests for _validate_audio_stream helper."""

    def test_validate_audio_stream_raises_when_no_audio(self, tmp_path: Path) -> None:
        """Should raise MediaError when no audio stream is present."""
        test_file = tmp_path / "video_only.mp4"
        streams = [{"codec_type": "video", "codec_name": "h264"}]

        with pytest.raises(MediaError, match="No audio stream"):
            _validate_audio_stream(streams, test_file)

    def test_validate_audio_stream_accepts_audio_stream(self, tmp_path: Path) -> None:
        """Should not raise when at least one audio stream is present."""
        test_file = tmp_path / "audio.mp3"
        streams = [{"codec_type": "audio", "codec_name": "mp3"}]

        _validate_audio_stream(streams, test_file)


class TestParseDuration:
    """Tests for ffprobe duration parsing."""

    def test_parse_duration_returns_float_for_positive_value(self) -> None:
        """Should parse positive duration values."""
        assert _parse_duration("10.5") == 10.5

    def test_parse_duration_returns_none_for_invalid_values(self) -> None:
        """Should ignore invalid, zero, and negative duration values."""
        assert _parse_duration("N/A") is None
        assert _parse_duration(None) is None
        assert _parse_duration("0") is None
        assert _parse_duration("-1.0") is None
        assert _parse_duration("inf") is None
        assert _parse_duration("nan") is None


class TestProbe:
    """Tests for probe() function."""

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_returns_media_info_for_valid_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should return MediaInfo for valid file with ffprobe output."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {
                "duration": "180.5",
                "format_name": "mp3",
            },
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "44100",
                    "channels": 2,
                }
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        result = probe(test_file)

        assert isinstance(result, MediaInfo)
        assert result.duration == 180.5
        assert result.format == "mp3"
        assert result.codec == "mp3"
        assert result.sample_rate == 44100
        assert result.channels == 2

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_invalid_input_for_missing_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should raise InvalidInputError for missing file."""
        missing_file = tmp_path / "nonexistent.mp3"

        with pytest.raises(InvalidInputError) as exc_info:
            probe(missing_file)

        assert exc_info.value.error_code == "AUD-002"
        mock_run.assert_not_called()

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_media_error_for_ffprobe_not_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should raise MediaError when ffprobe is not found."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        mock_run.side_effect = FileNotFoundError("ffprobe not found")

        with pytest.raises(MediaError) as exc_info:
            probe(test_file, ffprobe_path="/missing/ffprobe")

        assert exc_info.value.error_code == "AUD-402"
        assert "not found" in exc_info.value.message.lower()

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_media_error_for_ffprobe_failure(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should raise MediaError when ffprobe returns non-zero."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Invalid data found when processing input"
        )

        with pytest.raises(MediaError) as exc_info:
            probe(test_file)

        assert exc_info.value.error_code == "AUD-402"
        assert exc_info.value.context is not None
        assert "return_code" in exc_info.value.context

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_media_error_for_invalid_json_output(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should raise MediaError when ffprobe returns invalid JSON."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        mock_run.return_value = MagicMock(returncode=0, stdout="not valid json{{{", stderr="")

        with pytest.raises(MediaError) as exc_info:
            probe(test_file)

        assert exc_info.value.error_code == "AUD-402"
        assert "parse" in exc_info.value.message.lower()

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_extracts_all_fields_from_json(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should extract duration, format, codec, sample_rate, channels."""
        test_file = tmp_path / "video.mp4"
        test_file.write_text("fake video")

        ffprobe_output = {
            "format": {
                "duration": "3600.123",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            },
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                },
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        result = probe(test_file)

        assert result.duration == 3600.123
        assert result.format == "mov,mp4,m4a,3gp,3g2,mj2"
        assert result.codec == "aac"
        assert result.sample_rate == 48000
        assert result.channels == 2

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_uses_custom_ffprobe_path(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should use custom ffprobe path when provided."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        probe(test_file, ffprobe_path="/custom/path/ffprobe")

        call_args = mock_run.call_args
        assert "/custom/path/ffprobe" in call_args[0][0]

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_handles_duration_from_streams(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should calculate duration from streams if not in format."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"format_name": "mp3"},  # No duration
            "streams": [
                {"codec_type": "audio", "duration": "100.5"},
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        result = probe(test_file)

        assert result.duration == 100.5

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_falls_back_to_stream_duration_when_format_duration_invalid(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Regression: invalid format duration should not escape as ValueError."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "N/A", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "duration": "12.5", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        result = probe(test_file)

        assert result.duration == 12.5

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_handles_missing_audio_codec(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should handle files without audio stream codec."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [
                {"codec_type": "audio"},
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        result = probe(test_file)

        assert result.duration == 10.0
        assert result.codec is None
        assert result.sample_rate is None
        assert result.channels is None

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_when_no_audio_stream(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Regression: transcription inputs must contain at least one audio stream."""
        test_file = tmp_path / "video_only.mp4"
        test_file.write_text("fake video")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp4"},
            "streams": [{"codec_type": "video", "codec_name": "h264"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        with pytest.raises(MediaError, match="No audio stream"):
            probe(test_file)

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_timeout_parameter(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should use custom timeout when provided."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        probe(test_file, timeout=60)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("audiocore.media.probe.subprocess.run")
    @pytest.mark.parametrize("timeout", [0.0, -1.0, float("nan"), float("inf")])
    def test_probe_rejects_invalid_timeout(
        self, mock_run: MagicMock, tmp_path: Path, timeout: float
    ) -> None:
        """timeout must be finite and positive before invoking ffprobe."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        with pytest.raises(InvalidInputError) as exc_info:
            probe(test_file, timeout=timeout)

        assert "timeout" in str(exc_info.value)
        mock_run.assert_not_called()

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_on_timeout_expired(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should raise MediaError on subprocess timeout."""
        test_file = tmp_path / "large.mp3"
        test_file.write_text("fake audio")

        mock_run.side_effect = TimeoutExpired(cmd="ffprobe", timeout=30)

        with pytest.raises(MediaError) as exc_info:
            probe(test_file, timeout=30)

        assert exc_info.value.error_code == "AUD-402"
        assert "timed out" in exc_info.value.message.lower()
        assert str(test_file) in str(exc_info.value.context.get("file_path", ""))

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_raises_on_missing_duration(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should raise MediaError when duration cannot be determined."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"format_name": "mp3"},  # No duration
            "streams": [],  # No streams with duration
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        with pytest.raises(MediaError) as exc_info:
            probe(test_file)

        assert exc_info.value.error_code == "AUD-402"
        assert "duration" in exc_info.value.message.lower()

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_accepts_string_path(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should accept string path in addition to Path object."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        # Should work with string
        result = probe(str(test_file))

        assert isinstance(result, MediaInfo)
        assert result.duration == 10.0

    @patch("audiocore.media.probe.subprocess.run")
    def test_probe_handles_invalid_sample_rate_and_channels(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should handle invalid sample_rate and channels values gracefully."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "mp3",
                    "sample_rate": "invalid",
                    "channels": "not_a_number",
                }
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        result = probe(test_file)

        assert result.duration == 10.0
        assert result.codec == "mp3"
        assert result.sample_rate is None  # Invalid value should be None
        assert result.channels is None  # Invalid value should be None


class TestProbeCommand:
    """Tests for ffprobe command construction."""

    @patch("audiocore.media.probe.subprocess.run")
    def test_command_includes_quiet_flag(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should include -v quiet flag in command."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        probe(test_file)

        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args
        assert "quiet" in call_args

    @patch("audiocore.media.probe.subprocess.run")
    def test_command_includes_json_output(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Should include -print_format json flag in command."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        probe(test_file)

        call_args = mock_run.call_args[0][0]
        assert "-print_format" in call_args
        assert "json" in call_args

    @patch("audiocore.media.probe.subprocess.run")
    def test_command_includes_show_format_and_streams(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Should include -show_format and -show_streams flags."""
        test_file = tmp_path / "test.mp3"
        test_file.write_text("fake audio")

        ffprobe_output = {
            "format": {"duration": "10.0", "format_name": "mp3"},
            "streams": [{"codec_type": "audio", "codec_name": "mp3"}],
        }
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(ffprobe_output), stderr=""
        )

        probe(test_file)

        call_args = mock_run.call_args[0][0]
        assert "-show_format" in call_args
        assert "-show_streams" in call_args
