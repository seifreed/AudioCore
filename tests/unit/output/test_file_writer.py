"""Unit tests for file_writer module."""

import sys
import tempfile
from io import StringIO
from pathlib import Path

import pytest

from audiocore.errors.output import OutputFileExistsError
from audiocore.output.file_writer import OutputFileConfig, write_output


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
        with pytest.raises(Exception):  # Pydantic ValidationError
            OutputFileConfig(unknown_field="value")  # type: ignore

    def test_forbid_extra_fields(self) -> None:
        """Extra fields are forbidden."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            OutputFileConfig(extra="data")  # type: ignore


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

        # Atomic write should fail with OSError when parent doesn't exist
        with pytest.raises(OSError):
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


class TestAtomicWriteFailure:
    """Tests for atomic write failure handling."""

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
            with pytest.raises(OSError) as exc_info:
                write_output("Content", output_path, OutputFileConfig(overwrite=True))

            # Verify no temp files left
            temp_files = list(readonly_dir.glob("*.tmp"))
            assert len(temp_files) == 0

        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)
