"""Unit tests for file_writer module."""

import sys
from io import StringIO
from pathlib import Path

import pytest
from pydantic import ValidationError

from audiocore.errors.output import OutputDirectoryError, OutputFileExistsError
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.output.file_writer import (
    OutputFileConfig,
    format_and_write,
    write_output,
)
from audiocore.types import BackendType, OutputFormat


class TestOutputFileConfig:
    """Tests for OutputFileConfig Pydantic model."""

    def test_default_values(self) -> None:
        """Default config uses safe defaults."""
        config = OutputFileConfig()
        assert config.overwrite is False
        assert config.create_dirs is True
        assert config.encoding == "utf-8"

    def test_custom_values(self) -> None:
        """Custom values override defaults."""
        config = OutputFileConfig(overwrite=True, create_dirs=False, encoding="ascii")
        assert config.overwrite is True
        assert config.create_dirs is False
        assert config.encoding == "ascii"

    def test_strict_mode_rejects_unknown_fields(self) -> None:
        """Strict mode rejects unknown fields."""
        with pytest.raises(ValidationError):
            OutputFileConfig(unknown_field="value")  # type: ignore

    def test_forbid_extra_fields(self) -> None:
        """Extra fields are forbidden."""
        with pytest.raises(ValidationError):
            OutputFileConfig(extra="data")  # type: ignore

    def test_blank_encoding_rejected(self) -> None:
        """Regression: blank encodings should fail at config validation."""
        with pytest.raises(ValidationError):
            OutputFileConfig(encoding="   ")

    def test_unknown_encoding_rejected(self) -> None:
        """Regression: unknown encodings should fail before writing."""
        with pytest.raises(ValidationError):
            OutputFileConfig(encoding="not-a-real-codec")

    def test_encoding_is_stripped(self) -> None:
        """Surrounding whitespace in encoding names should be normalized."""
        config = OutputFileConfig(encoding=" utf-8 ")
        assert config.encoding == "utf-8"


class TestWriteOutput:
    """Tests for write_output function."""

    def test_write_creates_file(self, tmp_path: Path) -> None:
        """write_output creates a file with given content."""
        output_path = tmp_path / "output.txt"
        result = write_output("Hello world", output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_text() == "Hello world"

    def test_write_to_nested_directory(self, tmp_path: Path) -> None:
        """write_output creates parent directories."""
        output_path = tmp_path / "subdir" / "nested" / "output.txt"
        result = write_output("Content", output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_text() == "Content"
        assert output_path.parent.exists()

    def test_atomic_write_no_leftover_temp_file(self, tmp_path: Path) -> None:
        """Atomic write cleans up temp file after success."""
        output_path = tmp_path / "output.txt"
        write_output("Test content", output_path)

        # Check no .tmp files left
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_write_existing_file_raises_error(self, tmp_path: Path) -> None:
        """Writing to existing file raises OutputFileExistsError when overwrite=False."""
        output_path = tmp_path / "existing.txt"
        output_path.write_text("Original")

        with pytest.raises(OutputFileExistsError) as exc_info:
            write_output("New content", output_path, OutputFileConfig(overwrite=False))

        assert "already exists" in str(exc_info.value)
        assert str(output_path) in str(exc_info.value)

    def test_overwrite_true_replaces_file(self, tmp_path: Path) -> None:
        """overwrite=True replaces existing file."""
        output_path = tmp_path / "existing.txt"
        output_path.write_text("Original")

        config = OutputFileConfig(overwrite=True)
        result = write_output("New content", output_path, config)

        assert result == output_path
        assert output_path.read_text() == "New content"

    def test_overwrite_false_preserves_file(self, tmp_path: Path) -> None:
        """overwrite=False preserves existing file and raises error."""
        output_path = tmp_path / "existing.txt"
        output_path.write_text("Original")

        config = OutputFileConfig(overwrite=False)
        with pytest.raises(OutputFileExistsError):
            write_output("New content", output_path, config)

        # Original preserved
        assert output_path.read_text() == "Original"

    def test_custom_encoding(self, tmp_path: Path) -> None:
        """Custom encoding is respected."""
        output_path = tmp_path / "encoded.txt"
        content = "Héllo Wörld"

        config = OutputFileConfig(encoding="utf-8")
        write_output(content, output_path, config)

        assert output_path.read_text(encoding="utf-8") == content

    def test_create_dirs_false_fails_on_missing_directory(self, tmp_path: Path) -> None:
        """create_dirs=False fails if parent directory doesn't exist."""
        output_path = tmp_path / "nonexistent" / "output.txt"

        # Should raise OutputDirectoryError with actionable message
        with pytest.raises(OutputDirectoryError, match="Parent directory does not exist"):
            write_output("Content", output_path, OutputFileConfig(create_dirs=False))

    def test_write_empty_content(self, tmp_path: Path) -> None:
        """Empty content creates empty file."""
        output_path = tmp_path / "empty.txt"
        write_output("", output_path)

        assert output_path.exists()
        assert output_path.read_text() == ""

    def test_string_path_converted_to_path(self, tmp_path: Path) -> None:
        """String path is converted to Path object."""
        output_str = str(tmp_path / "string_path.txt")
        result = write_output("Content", output_str)

        assert isinstance(result, Path)
        assert result.exists()
        assert result.read_text() == "Content"

    def test_output_path_directory_raises_directory_error(self, tmp_path: Path) -> None:
        """An existing directory is not a valid output file path."""
        with pytest.raises(OutputDirectoryError, match="not a file"):
            write_output("Content", tmp_path, OutputFileConfig(overwrite=True))

    def test_parent_path_file_raises_directory_error(self, tmp_path: Path) -> None:
        """Parent path must be a directory before creating the output file."""
        parent_file = tmp_path / "parent.txt"
        parent_file.write_text("not a directory")
        output_path = parent_file / "output.txt"

        with pytest.raises(OutputDirectoryError, match="Parent path is not a directory"):
            write_output("Content", output_path)


class TestStdoutOutput:
    """Tests for stdout (path=None) handling."""

    def test_write_to_stdout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """path=None writes to stdout."""
        captured = StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        result = write_output("Hello stdout", None)

        assert result is None
        assert captured.getvalue() == "Hello stdout"

    def test_stdout_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Writing to stdout returns None."""
        captured = StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        result = write_output("Any content", None)

        assert result is None


class TestOutputFileExistsError:
    """Tests for OutputFileExistsError exception."""

    def test_error_code_is_aud_600(self) -> None:
        """OutputFileExistsError has error code AUD-600."""
        assert OutputFileExistsError.error_code == "AUD-600"

    def test_error_includes_context(self) -> None:
        """Error includes file path in context."""
        error = OutputFileExistsError(
            "File exists",
            context={"file_path": "/path/to/file.txt"},
        )

        assert error.context["file_path"] == "/path/to/file.txt"
        assert "File exists" in str(error)

    def test_error_default_suggestion(self) -> None:
        """Error provides default suggestions."""
        error = OutputFileExistsError("File exists")

        assert len(error.suggestions) == 2
        assert "overwrite=True" in error.suggestions[0]

    def test_error_custom_suggestions(self) -> None:
        """Error can have custom suggestions."""
        error = OutputFileExistsError(
            "File exists",
            suggestions=["Use different path"],
        )

        assert error.suggestions == ["Use different path"]

    def test_error_inherits_from_audiocore_error(self) -> None:
        """OutputFileExistsError inherits from AudioCoreError."""
        from audiocore.errors.base import AudioCoreError

        error = OutputFileExistsError("Test")
        assert isinstance(error, AudioCoreError)


class TestOutputDirectoryError:
    """Tests for OutputDirectoryError exception."""

    def test_error_code_is_aud_601(self) -> None:
        """OutputDirectoryError has error code AUD-601."""
        assert OutputDirectoryError.error_code == "AUD-601"

    def test_error_inherits_from_audiocore_error(self) -> None:
        """OutputDirectoryError inherits from AudioCoreError."""
        from audiocore.errors.base import AudioCoreError

        error = OutputDirectoryError("Test")
        assert isinstance(error, AudioCoreError)

    def test_error_default_suggestion(self) -> None:
        """Error provides default suggestions about creating directories."""
        error = OutputDirectoryError("Dir missing")

        assert len(error.suggestions) == 2
        assert "create_dirs" in error.suggestions[0].lower()


class TestAtomicWriteFailure:
    """Tests for atomic write failure handling."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows does not support Unix-style chmod for read-only directories",
    )
    def test_temp_file_cleaned_on_write_failure(self, tmp_path: Path) -> None:
        """Temp file is cleaned up if write fails."""
        # Create a read-only directory to force write failure
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        output_path = readonly_dir / "output.txt"

        # Make directory read-only (Unix)
        try:
            readonly_dir.chmod(0o444)

            # Try to create a file in read-only dir
            # This should fail during temp file creation
            with pytest.raises(OSError):
                write_output("Content", output_path, OutputFileConfig(overwrite=True))

            # Verify no temp files left
            temp_files = list(readonly_dir.glob("*.tmp"))
            assert len(temp_files) == 0

        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestFormatAndWrite:
    """Tests for format_and_write function."""

    def test_detect_srt_from_extension(self, tmp_path: Path) -> None:
        """format_and_write detects SRT format from .srt extension."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        output_path = tmp_path / "output.srt"
        format_and_write(result, TranscriptionOptions(), output_path)

        content = output_path.read_text()
        assert "1\n" in content  # SRT numbering
        assert "00:00:00,000 --> 00:00:05,000" in content  # SRT timestamp format (comma)
        assert "Hello" in content

    def test_detect_vtt_from_extension(self, tmp_path: Path) -> None:
        """format_and_write detects VTT format from .vtt extension."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        output_path = tmp_path / "output.vtt"
        format_and_write(result, TranscriptionOptions(), output_path)

        content = output_path.read_text()
        assert content.startswith("WEBVTT\n")
        assert "00:00:00.000 --> 00:00:05.000" in content  # VTT timestamp format (period)
        assert "Hello" in content

    def test_detect_json_from_extension(self, tmp_path: Path) -> None:
        """format_and_write detects JSON format from .json extension."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        output_path = tmp_path / "output.json"
        format_and_write(result, TranscriptionOptions(), output_path)

        content = output_path.read_text()
        assert '"segments"' in content
        assert '"text": "Hello"' in content

    def test_detect_text_from_extension(self, tmp_path: Path) -> None:
        """format_and_write detects TEXT format from .txt extension."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        output_path = tmp_path / "output.txt"
        format_and_write(result, TranscriptionOptions(), output_path)

        content = output_path.read_text()
        assert "[00:00:00.000] Hello" in content

    def test_unknown_extension_uses_options_format(self, tmp_path: Path) -> None:
        """Unknown extension falls back to options.output_format."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        # Use .unknown extension with SRT format in options
        options = TranscriptionOptions(output_format=OutputFormat.SRT)
        output_path = tmp_path / "output.unknown"
        format_and_write(result, options, output_path)

        content = output_path.read_text()
        assert "1\n" in content  # SRT numbering
        assert "00:00:00,000 --> 00:00:05,000" in content  # SRT format

    def test_stdout_uses_options_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """path=None uses options.output_format."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        captured = StringIO()
        monkeypatch.setattr(sys, "stdout", captured)

        # Use VTT format for stdout
        options = TranscriptionOptions(output_format=OutputFormat.VTT)
        result_path = format_and_write(result, options, None)

        assert result_path is None
        assert captured.getvalue().startswith("WEBVTT\n")

    def test_respects_overwrite_config(self, tmp_path: Path) -> None:
        """format_and_write respects overwrite config."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=10.0, text="New")],
            media_info=MediaInfo(duration=10.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        output_path = tmp_path / "output.txt"
        output_path.write_text("Original")

        # Should raise error with overwrite=False (default)
        with pytest.raises(OutputFileExistsError):
            format_and_write(result, TranscriptionOptions(), output_path)

        # Should succeed with overwrite=True
        config = OutputFileConfig(overwrite=True)
        format_and_write(result, TranscriptionOptions(), output_path, config)
        assert "New" in output_path.read_text()

    def test_creates_directories(self, tmp_path: Path) -> None:
        """format_and_write creates directories when needed."""
        result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        output_path = tmp_path / "nested" / "dir" / "output.srt"
        format_and_write(result, TranscriptionOptions(), output_path)

        assert output_path.exists()
        assert "Test" in output_path.read_text()
