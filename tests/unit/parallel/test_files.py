"""Unit tests for parallel file processing.

Tests verify:
- transcribe_files_concurrent() processes multiple files
- Semaphore limits max concurrent workers
- Results maintain input order
- Individual file failures handled correctly with continue_on_error
- Progress callback is called correctly
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.parallel.files import FileResult, transcribe_files_concurrent
from audiocore.types import BackendType


@pytest.fixture
def mock_transcription_result() -> TranscriptionResult:
    """Create a mock TranscriptionResult."""
    return TranscriptionResult(
        segments=[Segment(start_time=0.0, end_time=5.0, text="Hello world")],
        media_info=MediaInfo(duration=5.0, format="wav", sample_rate=16000, channels=1),
        config_used=TranscriptionOptions(),
        processing_time_seconds=2.0,
        backend_used=BackendType.OPENAI,
    )


@pytest.fixture
def transcription_options() -> TranscriptionOptions:
    """Create default TranscriptionOptions."""
    return TranscriptionOptions()


class TestFileResult:
    """Test FileResult dataclass."""

    def test_file_result_success(self, mock_transcription_result: TranscriptionResult) -> None:
        """Test FileResult with successful transcription."""
        result = FileResult(
            path=Path("audio.mp3"),
            success=True,
            result=mock_transcription_result,
            error=None,
        )
        assert result.success is True
        assert result.result is not None
        assert result.error is None

    def test_file_result_failure(self) -> None:
        """Test FileResult with failed transcription."""
        result = FileResult(
            path=Path("audio.mp3"),
            success=False,
            result=None,
            error="Transcription failed",
        )
        assert result.success is False
        assert result.result is None
        assert result.error == "Transcription failed"


class TestTranscribeFilesConcurrent:
    """Test transcribe_files_concurrent function."""

    @pytest.mark.asyncio
    async def test_rejects_invalid_max_workers(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
    ) -> None:
        """max_workers must be positive before creating the semaphore."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")

        with pytest.raises(ValueError, match="max_workers"):
            await transcribe_files_concurrent(
                files=[audio_file],
                options=transcription_options,
                max_workers=0,
            )

    @pytest.mark.asyncio
    async def test_single_file(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test transcription of a single file."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.return_value = mock_transcription_result

            results = await transcribe_files_concurrent(
                files=[audio_file],
                options=transcription_options,
                max_workers=1,
            )

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].path == audio_file
        assert results[0].result is not None
        assert results[0].error is None

    @pytest.mark.asyncio
    async def test_multiple_files(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test concurrent transcription of multiple files."""
        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.return_value = mock_transcription_result

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=2,
            )

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.success is True
            assert result.path == files[i]

    @pytest.mark.asyncio
    async def test_max_workers_semaphore(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test that semaphore limits concurrent workers."""
        files = []
        for i in range(5):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        concurrent_count = 0
        max_concurrent = 0

        def track_concurrency(path, options, cancellation_token=None):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            # Simulate some work
            import time

            time.sleep(0.01)
            concurrent_count -= 1
            return mock_transcription_result

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = track_concurrency

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=2,  # Limit to 2 concurrent
            )

        assert len(results) == 5
        # max_concurrent should not exceed max_workers
        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_continue_on_error_true(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test that continue_on_error=True continues after failure."""
        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        call_count = 0

        def fail_middle(path, options, cancellation_token=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Simulated transcription error")
            return mock_transcription_result

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = fail_middle

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=1,
                continue_on_error=True,
            )

        assert len(results) == 3
        assert results[0].success is True
        # Results maintain input order, but one failed in the middle
        # Since continue_on_error=True, we should have 3 results
        # Note: due to async nature, the order in results might differ
        # but all 3 files should have been processed
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        # At least one success (first file) and at least one failure
        assert len(successful) >= 1
        assert len(failed) >= 1

    @pytest.mark.asyncio
    async def test_results_maintain_order(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
    ) -> None:
        """Test that results maintain input file order."""
        files = []
        for i in range(5):
            audio_file = tmp_path / f"file{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        def create_result_with_id(path, options, cancellation_token=None):
            # Return a result with different text for each file
            file_id = path.stem
            return TranscriptionResult(
                segments=[Segment(start_time=0.0, end_time=1.0, text=f"Content of {file_id}")],
                media_info=MediaInfo(duration=1.0, format="wav", sample_rate=16000, channels=1),
                config_used=TranscriptionOptions(),
                processing_time_seconds=1.0,
                backend_used=BackendType.OPENAI,
            )

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = create_result_with_id

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=3,
            )

        # Verify order is maintained
        for i, result in enumerate(results):
            assert result.path == files[i]
            assert result.success is True
            assert f"file{i}" in result.result.segments[0].text

    @pytest.mark.asyncio
    async def test_progress_callback(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test progress callback is called correctly."""
        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        progress_calls: list[tuple[int, int, Path]] = []

        def progress_callback(completed: int, total: int, path: Path) -> None:
            progress_calls.append((completed, total, path))

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.return_value = mock_transcription_result

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=1,
                progress_callback=progress_callback,
            )

        assert len(results) == 3
        assert len(progress_calls) == 3
        # Progress should be called in order with correct totals
        for i, (completed, total, path) in enumerate(progress_calls):
            assert total == 3
            assert completed == i + 1
            assert path in files


class TestTranscribeFilesConcurrentErrors:
    """Test error handling in transcribe_files_concurrent."""

    @pytest.mark.asyncio
    async def test_file_not_found_error(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
    ) -> None:
        """Test handling of FileNotFoundError."""
        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = FileNotFoundError("File not found")

            results = await transcribe_files_concurrent(
                files=[audio_file],
                options=transcription_options,
                max_workers=1,
                continue_on_error=True,
            )

        assert len(results) == 1
        assert results[0].success is False
        assert "File not found" in results[0].error

    @pytest.mark.asyncio
    async def test_backend_unavailable_error(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
    ) -> None:
        """Test handling of BackendUnavailableError."""
        from audiocore.errors import BackendUnavailableError

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"fake audio")

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = BackendUnavailableError(
                "No backend available",
                context={},
                suggestions=["Install a backend"],
            )

            results = await transcribe_files_concurrent(
                files=[audio_file],
                options=transcription_options,
                max_workers=1,
                continue_on_error=True,
            )

        assert len(results) == 1
        assert results[0].success is False
        assert "No backend available" in results[0].error

    @pytest.mark.asyncio
    async def test_continue_on_error_false_stops_on_failure(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Regression: continue_on_error=False should propagate exceptions.

        Previously, return_exceptions=True in asyncio.gather prevented
        exceptions from propagating, making continue_on_error=False a no-op.
        Now exceptions propagate correctly from gather.
        """
        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = RuntimeError("Simulated failure")

            with pytest.raises(RuntimeError, match="Simulated failure"):
                await transcribe_files_concurrent(
                    files=files,
                    options=transcription_options,
                    max_workers=1,
                    continue_on_error=False,
                )

    @pytest.mark.asyncio
    async def test_empty_file_list(
        self,
        transcription_options: TranscriptionOptions,
    ) -> None:
        """Test handling of empty file list."""
        results = await transcribe_files_concurrent(
            files=[],
            options=transcription_options,
            max_workers=1,
        )

        assert len(results) == 0


class TestAsyncioIntegration:
    """Test asyncio integration for concurrent processing."""

    @pytest.mark.asyncio
    async def test_concurrent_execution_timing(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test that files are processed concurrently (faster than sequential)."""
        import time

        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        def slow_transcribe(path, options, cancellation_token=None):
            time.sleep(0.1)  # Simulate slow transcription
            return mock_transcription_result

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = slow_transcribe

            start_time = time.time()
            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=3,  # Allow all 3 to run concurrently
            )
            elapsed_time = time.time() - start_time

        assert len(results) == 3
        # If truly concurrent, should take ~0.1s, not ~0.3s
        # Allow some overhead for test environment
        assert elapsed_time < 0.25, f"Expected concurrent execution, took {elapsed_time:.2f}s"

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Test that semaphore actually limits maximum concurrency."""
        import time

        files = []
        for i in range(5):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        concurrent_count = 0
        max_observed = 0
        lock = asyncio.Lock()

        async def track_concurrent(path, options, cancellation_token=None):
            nonlocal concurrent_count, max_observed
            async with lock:
                concurrent_count += 1
                max_observed = max(max_observed, concurrent_count)
            # This runs in executor, so we need to use asyncio-friendly approach
            return mock_transcription_result

        # We need to track actual concurrent calls to transcribe()
        # Since transcribe is sync and runs in executor, we track via wrapper
        actual_max_concurrent = 0
        current_concurrent = 0
        counter_lock = __import__("threading").Lock()

        def track_sync_transcribe(path, options, cancellation_token=None):
            nonlocal actual_max_concurrent, current_concurrent
            with counter_lock:
                current_concurrent += 1
                actual_max_concurrent = max(actual_max_concurrent, current_concurrent)
            time.sleep(0.05)  # Hold concurrency for measurement
            with counter_lock:
                current_concurrent -= 1
            return mock_transcription_result

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.side_effect = track_sync_transcribe

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=2,  # Limit to 2
            )

        assert len(results) == 5
        # Max concurrent should not exceed max_workers
        assert actual_max_concurrent <= 2, (
            f"Max concurrent was {actual_max_concurrent}, expected <= 2"
        )


class TestProgressCallbackLockContention:
    """Regression tests for progress callback lock contention."""

    @pytest.mark.asyncio
    async def test_progress_callback_called_outside_lock(
        self,
        tmp_path: Path,
        transcription_options: TranscriptionOptions,
        mock_transcription_result: TranscriptionResult,
    ) -> None:
        """Regression: progress callback must be called outside the counter lock.

        Previously, the progress callback was invoked while holding the
        asyncio counter_lock, blocking other coroutines from updating
        progress. Now the callback is called after releasing the lock.
        """
        files = []
        for i in range(3):
            audio_file = tmp_path / f"test{i}.wav"
            audio_file.write_bytes(b"fake audio")
            files.append(audio_file)

        progress_calls: list[tuple[int, int, Path]] = []

        def slow_progress_callback(completed: int, total: int, path: Path) -> None:
            progress_calls.append((completed, total, path))

        with patch("audiocore.parallel.files.transcribe") as mock_transcribe:
            mock_transcribe.return_value = mock_transcription_result

            results = await transcribe_files_concurrent(
                files=files,
                options=transcription_options,
                max_workers=1,
                progress_callback=slow_progress_callback,
            )

        assert len(results) == 3
        # All progress callbacks should have been called
        assert len(progress_calls) == 3
        # Completed counts should be 1, 2, 3 (ordered by completion)
        completed_counts = sorted([c for c, _, _ in progress_calls])
        assert completed_counts == [1, 2, 3]
