"""File-level concurrent processing for transcription.

This module provides concurrent transcription of multiple audio/video files
using asyncio and a semaphore to limit concurrency.

The implementation uses asyncio.gather() to process files concurrently
with a configurable worker limit, ensuring memory and resource control.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from audiocore.api.transcribe import _get_executor, transcribe

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from audiocore.models import TranscriptionOptions, TranscriptionResult


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
    semaphore = asyncio.Semaphore(max_workers)
    results: list[FileResult | None] = [None] * len(files)
    completed_count = 0
    total_count = len(files)
    counter_lock = asyncio.Lock()

    async def transcribe_single_file(
        index: int,
        file_path: Path,
    ) -> FileResult:
        """Transcribe a single file with semaphore control.

        Args:
            index: Index in results list for order preservation.
            file_path: Path to the file to transcribe.

        Returns:
            FileResult with success/failure status.
        """
        nonlocal completed_count

        async with semaphore:
            try:
                # Run synchronous transcribe in the shared thread pool executor
                # to avoid creating too many threads when used alongside async_transcribe
                result = await asyncio.get_running_loop().run_in_executor(
                    _get_executor(),
                    lambda: transcribe(path=file_path, options=options),
                )

                # Update counter and call progress callback outside lock to avoid blocking
                if progress_callback:
                    async with counter_lock:
                        completed_count += 1
                        current_count = completed_count
                    # Call callback outside lock to avoid blocking other coroutines
                    progress_callback(current_count, total_count, file_path)

                return FileResult(
                    path=file_path,
                    success=True,
                    result=result,
                    error=None,
                )

            except Exception as e:
                # Extract error message
                error_message = str(e)

                if not continue_on_error:
                    # Re-raise to stop all processing
                    raise

                # Update progress even for failures (thread-safe counter update)
                if progress_callback:
                    async with counter_lock:
                        completed_count += 1
                        current_count = completed_count
                    # Call callback outside lock to avoid blocking other coroutines
                    progress_callback(current_count, total_count, file_path)

                return FileResult(
                    path=file_path,
                    success=False,
                    result=None,
                    error=error_message,
                )

    # Create tasks for all files
    tasks = [asyncio.create_task(transcribe_single_file(i, file)) for i, file in enumerate(files)]

    if continue_on_error:
        # Run all tasks to completion, collecting exceptions as results
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, task_result in enumerate(task_results):
            if isinstance(task_result, BaseException) and not isinstance(task_result, Exception):
                # CancelledError and other BaseExceptions (not Exception)
                results[i] = FileResult(
                    path=files[i],
                    success=False,
                    result=None,
                    error=f"Cancelled: {task_result}",
                )
            elif isinstance(task_result, Exception):
                results[i] = FileResult(
                    path=files[i],
                    success=False,
                    result=None,
                    error=str(task_result),
                )
            else:
                results[i] = task_result
    else:
        # Stop on first error: let exceptions propagate from gather
        try:
            task_results = await asyncio.gather(*tasks)
            for i, task_result in enumerate(task_results):
                results[i] = task_result
        except Exception:
            # Cancel any still-running tasks before re-raising
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Wait for cancellations to complete (suppress CancelledError)
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    # Validate all results are populated before returning
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
