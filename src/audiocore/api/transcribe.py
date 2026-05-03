"""
Public API transcribe functions.

This module provides the transcribe() and async_transcribe() functions
for end-users, wrapping the Pipeline class with convenient defaults.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from audiocore.backends import register_builtin_backends
from audiocore.errors import AudioCoreError
from audiocore.models import TranscriptionOptions, TranscriptionResult
from audiocore.pipeline import Pipeline

if TYPE_CHECKING:
    from pathlib import Path

    from audiocore.config import AppConfig
    from audiocore.pipeline.cancellation import CancellationToken
    from audiocore.pipeline.progress import ProgressCallback

# Register backends on module load
register_builtin_backends()

# Thread pool for async transcribe
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    """Get or create the thread pool executor for async operations."""
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="audiocore-")
    return _executor


def _cleanup_executor() -> None:
    """Shutdown the thread pool executor on program exit.

    Uses wait=True to allow in-flight tasks to complete gracefully,
    matching the behavior of the explicit shutdown_executor() call.
    """
    global _executor
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=True)
            _executor = None


# Register cleanup on module load
atexit.register(_cleanup_executor)


def transcribe(
    path: str | Path,
    options: TranscriptionOptions | None = None,
    config: AppConfig | None = None,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> TranscriptionResult:
    """Transcribe an audio/video file synchronously.

    This function provides a convenient one-line API for transcription.
    It creates a Pipeline instance with the given configuration and
    transcribes the file.

    Args:
        path: Path to the audio/video file to transcribe.
        options: Transcription options. If None, loads defaults from config
            or uses TranscriptionOptions() defaults.
        config: Application configuration. If None, loads from
            environment/TOML/defaults via load_config().
        progress_callback: Optional callback for progress notifications.
            Called with (stage, progress, message) at each stage transition.
        cancellation_token: Optional token for cancellation support.

    Returns:
        TranscriptionResult with segments, media info, and metadata.

    Raises:
        AudioCoreError: Base exception for all AudioCore errors.
        InvalidInputError: If input file not found.
        MediaFormatError: If input format not supported.
        MediaError: If media processing fails.
        VADError: If VAD processing fails.
        BackendUnavailableError: If no backend available.
        TranscriptionError: If transcription fails.
        ConfigurationError: If configuration is invalid.
        PipelineStageError: If a pipeline stage fails.
        PartialResultError: If partial transcription is available.
        CancelledError: If cancelled during execution.

    Example:
        >>> from audiocore import transcribe
        >>> result = transcribe("audio.mp3")
        >>> print(result.segments[0].text)

        >>> # With progress callback
        >>> def on_progress(stage, progress, message):
        ...     print(f"[{stage.value}] {progress:.0%}: {message}")
        >>> result = transcribe("audio.mp3", progress_callback=on_progress)

        >>> # With custom options
        >>> from audiocore import TranscriptionOptions, BackendType
        >>> options = TranscriptionOptions(backend=BackendType.OPENAI)
        >>> result = transcribe("audio.mp3", options=options)
    """
    # Lazy import to avoid circular import
    from audiocore.config import load_config

    # Load config if not provided
    if config is None:
        config = load_config()

    # Load options from config if not provided
    if options is None:
        options = TranscriptionOptions()

    # Create pipeline and transcribe
    pipeline = Pipeline(config=config)
    return pipeline.transcribe(
        path=path,
        options=options,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )


async def async_transcribe(
    path: str | Path,
    options: TranscriptionOptions | None = None,
    config: AppConfig | None = None,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
) -> TranscriptionResult:
    """Transcribe an audio/video file asynchronously.

    This function provides an async API for non-blocking transcription.
    It runs the synchronous transcribe() in a thread pool, allowing
    the event loop to remain responsive.

    Args:
        path: Path to the audio/video file to transcribe.
        options: Transcription options. If None, loads defaults from config
            or uses TranscriptionOptions() defaults.
        config: Application configuration. If None, loads from
            environment/TOML/defaults via load_config().
        progress_callback: Optional callback for progress notifications.
            Called from background thread, so callbacks should be thread-safe.
        cancellation_token: Optional token for cancellation support.

    Returns:
        TranscriptionResult with segments, media info, and metadata.

    Raises:
        AudioCoreError: Base exception for all AudioCore errors.
        InvalidInputError: If input file not found.
        MediaFormatError: If input format not supported.
        MediaError: If media processing fails.
        VADError: If VAD processing fails.
        BackendUnavailableError: If no backend available.
        TranscriptionError: If transcription fails.
        ConfigurationError: If configuration is invalid.
        PipelineStageError: If a pipeline stage fails.
        PartialResultError: If partial transcription is available.
        CancelledError: If cancelled during execution.
        asyncio.CancelledError: If asyncio cancellation is requested.

    Example:
        >>> import asyncio
        >>> from audiocore import async_transcribe
        >>>
        >>> result = asyncio.run(async_transcribe("audio.mp3"))
        >>> print(result.segments[0].text)

        >>> # Concurrent transcription
        >>> results = await asyncio.gather(
        ...     async_transcribe("audio1.mp3"),
        ...     async_transcribe("audio2.mp3"),
        ...     async_transcribe("audio3.mp3"),
        ... )
    """
    # Create a CancellationToken if none provided so cancellation always propagates
    from audiocore.pipeline.cancellation import CancellationToken

    own_token = cancellation_token is None
    if own_token:
        cancellation_token = CancellationToken()

    assert cancellation_token is not None

    # Get the thread pool executor
    executor = _get_executor()

    # Run synchronous transcribe in thread pool
    loop = asyncio.get_running_loop()

    try:
        result = await loop.run_in_executor(
            executor,
            transcribe,
            path,
            options,
            config,
            progress_callback,
            cancellation_token,
        )
        return result
    except asyncio.CancelledError:
        # Propagate cancellation to the running thread via CancellationToken
        # run_in_executor does NOT cancel the underlying thread, so we signal
        # the pipeline to stop via its cancellation token.
        cancellation_token.cancel()
        raise
    except AudioCoreError:
        # Re-raise AudioCore exceptions directly
        raise
    except Exception as e:
        # Wrap unexpected exceptions
        raise AudioCoreError(
            f"Unexpected error during transcription: {e}",
            context={"path": str(path)},
        ) from e


def shutdown_executor() -> None:
    """Shutdown the thread pool executor for async operations.

    Call this to clean up resources when done with async_transcribe.
    After calling this, async_transcribe will create a new executor.
    """
    global _executor
    with _executor_lock:
        if _executor is not None:
            _executor.shutdown(wait=True)
            _executor = None


__all__ = [
    "transcribe",
    "async_transcribe",
    "shutdown_executor",
]
