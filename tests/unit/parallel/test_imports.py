"""Unit tests for parallel module imports.

Tests verify:
- All exports are accessible from audiocore.parallel
- Exported items match expected names and types
"""



class TestParallelModuleImports:
    """Test parallel module exports."""

    def test_import_transcribe_files_concurrent(self) -> None:
        """Test transcribe_files_concurrent is importable."""
        from audiocore.parallel import transcribe_files_concurrent

        assert callable(transcribe_files_concurrent)

    def test_import_file_result(self) -> None:
        """Test FileResult is importable."""
        from audiocore.parallel import FileResult

        assert FileResult is not None
        # Should be a dataclass
        from dataclasses import is_dataclass

        assert is_dataclass(FileResult)

    def test_import_transcribe_segments_parallel(self) -> None:
        """Test transcribe_segments_parallel is importable."""
        from audiocore.parallel import transcribe_segments_parallel

        assert callable(transcribe_segments_parallel)

    def test_import_all_from_module(self) -> None:
        """Test __all__ exports are correctly defined."""
        from audiocore.parallel import __all__

        expected_exports = [
            "transcribe_files_concurrent",
            "FileResult",
            "transcribe_segments_parallel",
        ]

        assert set(__all__) == set(expected_exports)

    def test_module_docstring(self) -> None:
        """Test module has proper documentation."""
        import audiocore.parallel

        assert audiocore.parallel.__doc__ is not None
        assert "parallel" in audiocore.parallel.__doc__.lower()
        assert "concurrent" in audiocore.parallel.__doc__.lower()

    def test_file_result_from_import(self) -> None:
        """Test FileResult can be constructed after import."""
        from pathlib import Path

        from audiocore.parallel import FileResult

        result = FileResult(
            path=Path("test.mp3"),
            success=True,
            result=None,
            error=None,
        )
        assert result.success is True
        assert result.path == Path("test.mp3")

    def test_file_result_with_result(self) -> None:
        """Test FileResult with TranscriptionResult."""
        from pathlib import Path

        from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
        from audiocore.parallel import FileResult
        from audiocore.types import BackendType

        transcription_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Hello world")],
            media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
            config_used=TranscriptionOptions(),
            processing_time_seconds=2.0,
            backend_used=BackendType.OPENAI,
        )

        result = FileResult(
            path=Path("audio.mp3"),
            success=True,
            result=transcription_result,
            error=None,
        )

        assert result.success is True
        assert result.result is not None
        assert result.result.segments[0].text == "Hello world"
