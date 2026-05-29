"""Unit tests for ffmpeg/ffprobe argument-injection hardening (CWE-88).

as_file_argument neutralizes paths that would otherwise be parsed by
ffmpeg/ffprobe as option flags because they begin with '-'.
"""

from __future__ import annotations

from pathlib import Path

from audiocore.media.safe_args import as_file_argument


class TestAsFileArgument:
    """Tests for as_file_argument."""

    def test_plain_relative_path_unchanged(self) -> None:
        """A normal relative path is returned verbatim."""
        assert as_file_argument(Path("audio.wav")) == "audio.wav"

    def test_absolute_path_unchanged(self) -> None:
        """An absolute path never starts with '-' and is returned verbatim."""
        assert as_file_argument(Path("/tmp/audio.wav")) == "/tmp/audio.wav"

    def test_nested_relative_path_unchanged(self) -> None:
        """A nested relative path whose first char is not '-' is unchanged."""
        assert as_file_argument(Path("subdir/-weird.wav")) == "subdir/-weird.wav"

    def test_leading_dash_relative_path_is_prefixed(self) -> None:
        """A path starting with '-' is prefixed with './' so it is not an option."""
        assert as_file_argument(Path("-i.wav")) == "./-i.wav"

    def test_leading_dash_option_like_name_is_prefixed(self) -> None:
        """An option-like filename cannot be parsed as an ffmpeg flag."""
        result = as_file_argument(Path("-f"))
        assert not result.startswith("-")
        assert result == "./-f"

    def test_accepts_str_input(self) -> None:
        """A plain string path is handled the same as a Path."""
        assert as_file_argument("-evil.mp4") == "./-evil.mp4"
