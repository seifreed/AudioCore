"""File-level concurrent processing for transcription.

This module provides concurrent transcription of multiple audio/video files
using asyncio and a semaphore to limit concurrency.

The implementation uses asyncio.gather() to process files concurrently
with a configurable worker limit, ensuring memory and resource control.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from audiocore.api.transcribe import _get_executor, transcribe
from audiocore.pipeline.cancellation import CancelledError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from audiocore.config import AppConfig
    from audiocore.models import TranscriptionOptions, TranscriptionResult
    from audiocore.pipeline.cancellation import CancellationToken


@dataclass
class FileResult:
    """Result of transcribing a single file.

    Attributes:
        path: Path to the transcribed file.
        success: Whether transcription succeeded.
        result: TranscriptionResult if successful, None otherwise.
        error: Error message if failed, None otherwise.

    Example:
        >>> result = FileResult(
        ...     path=Path("audio.mp3"),
        ...     success=True,
        ...     result=transcription_result,
        ...     error=None
        ... )
        >>> if result.success:
        ...     print(result.result.segments[0].text)
    """

    path: Path
    success: bool
    result: TranscriptionResult | None
    error: str | None


async def transcribe_files_concurrent(
    files: list[Path],
    options: TranscriptionOptions,
    max_workers: int = 4,
    continue_on_error: bool = True,
    progress_callback: Callable[[int, int, Path], None] | None = None,
    cancellation_token: CancellationToken | None = None,
    config: AppConfig | None = None,
) -> list[FileResult]:
    """Transcribe multiple files concurrently with controlled parallelism.

    This function processes multiple audio/video files concurrently using
    asyncio, with a semaphore to limit the number of concurrent operations.
    Results are returned in the same order as the input files.

    Args:
        files: List of file paths to transcribe.
        options: Transcription options to use for all files.
        max_workers: Maximum number of concurrent transcription operations.
            Default is 4. Higher values may improve throughput but
            increase memory usage.
        continue_on_error: If True (default), continue processing remaining
            files when one fails. If False, stop on first error.
        progress_callback: Optional callback for progress updates.
            Called with (completed_count, total_count, current_path).
            Warning: this is a synchronous callback called from an async context.
            Keep it fast (avoid blocking I/O) to prevent stalling the event loop.
        cancellation_token: Optional token for cancellation support.
        config: Optional application configuration to pass to each transcription.

    Returns:
        List of FileResult objects in the same order as input files.
        Each result contains either a successful TranscriptionResult
        or an error message.

    Example:
        >>> import asyncio
        >>> from pathlib import Path
        >>> from audiocore.models import TranscriptionOptions
        >>> from audiocore.parallel import transcribe_files_concurrent
        >>>
        >>> files = [Path("audio1.mp3"), Path("audio2.mp3")]
        >>> options = TranscriptionOptions()
        >>> results = asyncio.run(transcribe_files_concurrent(files, options))
        >>> for result in results:
        ...     if result.success:
        ...         print(f"{result.path}: {len(result.result.segments)} segments")
        ...     else:
        ...         print(f"{result.path}: Error - {result.error}")
    """
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    semaphore = asyncio.Semaphore(max_workers)
    completed_count = 0
    total_count = len(files)
    counter_lock = asyncio.Lock()

    async def report_progress(file_path: Path) -> None:
        """Advance the completed counter and notify the progress callback."""
        nonlocal completed_count
        if not progress_callback:
            return
        try:
            async with counter_lock:
                completed_count += 1
                current_count = completed_count
            progress_callback(current_count, total_count, file_path)
        except Exception:
            logger.debug("Progress callback raised, ignoring", exc_info=True)

    def run_transcribe(file_path: Path) -> TranscriptionResult:
        """Run the synchronous transcribe with the optional config supplied."""
        if config is None:
            return transcribe(
                path=file_path, options=options, cancellation_token=cancellation_token
            )
        return transcribe(
            path=file_path,
            options=options,
            config=config,
            cancellation_token=cancellation_token,
        )

    async def transcribe_single_file(file_path: Path) -> FileResult:
        """Transcribe one file under the concurrency semaphore in the executor."""
        async with semaphore:
            try:
                # Run synchronous transcribe in the shared thread pool executor to
                # avoid spawning excess threads alongside async_transcribe.
                result = await asyncio.get_running_loop().run_in_executor(
                    _get_executor(max_workers=max_workers),
                    run_transcribe,
                    file_path,
                )
                await report_progress(file_path)
                return FileResult(path=file_path, success=True, result=result, error=None)
            except CancelledError:
                raise
            except Exception as e:
                if not continue_on_error:
                    raise
                await report_progress(file_path)
                return FileResult(path=file_path, success=False, result=None, error=str(e))

    tasks = [asyncio.create_task(transcribe_single_file(file)) for file in files]
    return await _collect_file_results(tasks, files, continue_on_error)


async def _collect_file_results(
    tasks: list[asyncio.Task[FileResult]],
    files: list[Path],
    continue_on_error: bool,
) -> list[FileResult]:
    """Await per-file tasks and assemble ordered FileResults.

    Control-flow exceptions (cancellation, KeyboardInterrupt, SystemExit) always
    propagate; per-file ``Exception``s become failure results only when
    ``continue_on_error`` is set. On fail-fast, still-running tasks are cancelled
    before re-raising.
    """
    results: list[FileResult | None] = [None] * len(files)

    if continue_on_error:
        task_results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, task_result in enumerate(task_results):
            if isinstance(task_result, CancelledError):
                raise task_result
            if isinstance(task_result, BaseException) and not isinstance(task_result, Exception):
                # Control-flow exceptions are not per-file failures and must not
                # be masked by continue_on_error.
                raise task_result
            if isinstance(task_result, Exception):
                results[i] = FileResult(
                    path=files[i], success=False, result=None, error=str(task_result)
                )
            else:
                results[i] = task_result
    else:
        try:
            for i, task_result in enumerate(await asyncio.gather(*tasks)):
                results[i] = task_result
        except BaseException:
            # Cancel still-running tasks before re-raising so nothing is orphaned.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    for i, result in enumerate(results):
        if result is None:
            results[i] = FileResult(
                path=files[i],
                success=False,
                result=None,
                error="Internal error: result was not populated",
            )

    return list(results)  # type: ignore[return-value]


__all__ = ["FileResult", "transcribe_files_concurrent"]
