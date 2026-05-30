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
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, TypeIs

from audiocore.backends import register_builtin_backends
from audiocore.errors import AudioCoreError
from audiocore.models import (
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
    transcription_options_from_config,
)
from audiocore.pipeline import Pipeline
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy

if TYPE_CHECKING:
    from collections.abc import Iterator

    from audiocore.config import AppConfig
    from audiocore.diarization import Diarizer
    from audiocore.parallel.files import FileResult
    from audiocore.pipeline.cancellation import CancellationToken
    from audiocore.pipeline.progress import ProgressCallback
    from audiocore.vad import VADModel
    from audiocore.vad.config import VADConfig

# Register backends on module load
register_builtin_backends()

# Thread pool for async transcribe
_executor: ThreadPoolExecutor | None = None
_executor_max_workers = 0
_retired_executors: list[ThreadPoolExecutor] = []
_executor_lock = threading.Lock()


def _get_executor(max_workers: int = 4) -> ThreadPoolExecutor:
    """Get or create the thread pool executor for async operations.

    Args:
        max_workers: Minimum number of threads needed by the caller.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")

    global _executor, _executor_max_workers
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="audiocore-")
            _executor_max_workers = max_workers
        elif max_workers > _executor_max_workers:
            _retired_executors.append(_executor)
            _executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="audiocore-")
            _executor_max_workers = max_workers
        return _executor


def _cleanup_executor() -> None:
    """Shutdown the thread pool executor on program exit.

    Uses wait=True to allow in-flight tasks to complete gracefully,
    matching the behavior of the explicit shutdown_executor() call.
    """
    global _executor, _executor_max_workers
    with _executor_lock:
        while _retired_executors:
            _retired_executors.pop().shutdown(wait=True)
        if _executor is not None:
            _executor.shutdown(wait=True)
            _executor = None
            _executor_max_workers = 0


# Register cleanup on module load
atexit.register(_cleanup_executor)


def _parse_backend(value: BackendType | str | None) -> BackendType | None:
    """Parse a public API backend override."""
    if value is None or isinstance(value, BackendType):
        return value
    if isinstance(value, str):
        return BackendType.parse(value)
    raise TypeError("backend must be a BackendType, string, or None")


def _parse_model_size(value: ModelSize | str | None) -> ModelSize | None:
    """Parse a public API model-size override."""
    if value is None or isinstance(value, ModelSize):
        return value
    if isinstance(value, str):
        return ModelSize.parse(value)
    raise TypeError("model_size must be a ModelSize, string, or None")


def _parse_output_format(value: OutputFormat | str | None) -> OutputFormat | None:
    """Parse a public API output-format override."""
    if value is None or isinstance(value, OutputFormat):
        return value
    if isinstance(value, str):
        return OutputFormat.parse(value)
    raise TypeError("output_format must be an OutputFormat, string, or None")


def _parse_backend_preference(
    value: SelectionPolicy | str | None,
) -> SelectionPolicy | None:
    """Parse a public API backend-preference override."""
    if value is None or isinstance(value, SelectionPolicy):
        return value
    if isinstance(value, str):
        return SelectionPolicy.parse(value)
    raise TypeError("backend_preference must be a SelectionPolicy, string, or None")


def _parse_strict_vad(value: bool | None) -> bool | None:
    """Validate a public API strict_vad override."""
    if value is None or isinstance(value, bool):
        return value
    raise TypeError("strict_vad must be a bool or None")


def _parse_vad_config(value: object | None) -> VADConfig | None:
    """Validate a public API VAD config override."""
    if value is None:
        return None
    from audiocore.vad.config import VADConfig

    if isinstance(value, VADConfig):
        return value
    raise TypeError("vad_config must be a VADConfig instance or None")


def _apply_vad_config(config: AppConfig, vad_config: object | None) -> AppConfig:
    """Return config with an optional public API VAD override applied."""
    parsed_vad_config = _parse_vad_config(vad_config)
    if parsed_vad_config is None:
        return config
    return config.model_copy(update={"vad": parsed_vad_config})


def _resolve_options(
    config: AppConfig,
    options: TranscriptionOptions | None,
    *,
    backend: BackendType | str | None = None,
    model_size: ModelSize | str | None = None,
    language: str | None = None,
    output_format: OutputFormat | str | None = None,
    backend_preference: SelectionPolicy | str | None = None,
    strict_vad: bool | None = None,
) -> TranscriptionOptions:
    """Build effective options from config/options plus public API overrides."""
    backend_override = _parse_backend(backend)
    model_size_override = _parse_model_size(model_size)
    output_format_override = _parse_output_format(output_format)
    backend_preference_override = _parse_backend_preference(backend_preference)
    strict_vad_override = _parse_strict_vad(strict_vad)

    if language is not None and not isinstance(language, str):
        raise TypeError("language must be a string or None")

    if options is None:
        resolved = transcription_options_from_config(
            config,
            backend=backend_override,
            model_size=model_size_override,
            language=language,
            output_format=output_format_override,
            backend_preference=backend_preference_override,
        )
    else:
        updates: dict[str, object] = {}
        if backend_override is not None:
            updates["backend"] = backend_override
        if model_size_override is not None:
            updates["model_size"] = model_size_override
        if language is not None:
            updates["language"] = language
        if output_format_override is not None:
            updates["output_format"] = output_format_override
        if backend_preference_override is not None:
            updates["backend_preference"] = backend_preference_override
        resolved = options.model_copy(update=updates) if updates else options

    if strict_vad_override is not None:
        resolved = resolved.model_copy(update={"strict_vad": strict_vad_override})

    return resolved


def _is_batch_path(
    path: object,
) -> TypeIs[list[str | Path] | tuple[str | Path, ...]]:
    """Return True for the public async batch path form."""
    return isinstance(path, (list, tuple))


def transcribe(
    path: str | Path,
    options: TranscriptionOptions | None = None,
    config: AppConfig | None = None,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
    *,
    backend: BackendType | str | None = None,
    model_size: ModelSize | str | None = None,
    language: str | None = None,
    output_format: OutputFormat | str | None = None,
    backend_preference: SelectionPolicy | str | None = None,
    strict_vad: bool | None = None,
    vad_config: VADConfig | None = None,
    vad_model: VADModel | None = None,
    diarizer: Diarizer | None = None,
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
        backend: Optional backend override (enum or string).
        model_size: Optional model-size override (enum or string).
        language: Optional language override.
        output_format: Optional output-format override (enum or string).
        backend_preference: Optional automatic backend selection preference.
        strict_vad: Optional VAD failure behavior override.
        vad_config: Optional VAD configuration override.
        vad_model: Optional custom VAD detector (``VADModel`` protocol) used for
            the speech-detection stage instead of the bundled Silero VAD.
        diarizer: Optional speaker diarizer (``Diarizer`` protocol); when set,
            transcribed segments are labeled with speaker turns.

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

        >>> # With convenience keyword options
        >>> result = transcribe("audio.mp3", backend="openai", language="es")
    """
    # Lazy import to avoid circular import
    from audiocore.config import load_config

    # Load config if not provided
    if config is None:
        config = load_config()
    config = _apply_vad_config(config, vad_config)

    options = _resolve_options(
        config,
        options,
        backend=backend,
        model_size=model_size,
        language=language,
        output_format=output_format,
        backend_preference=backend_preference,
        strict_vad=strict_vad,
    )

    # Create pipeline and transcribe
    pipeline = Pipeline(config=config, vad_model=vad_model, diarizer=diarizer)
    return pipeline.transcribe(
        path=path,
        options=options,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
    )


def stream_transcribe(
    path: str | Path,
    options: TranscriptionOptions | None = None,
    config: AppConfig | None = None,
    cancellation_token: CancellationToken | None = None,
    *,
    backend: BackendType | str | None = None,
    model_size: ModelSize | str | None = None,
    language: str | None = None,
    backend_preference: SelectionPolicy | str | None = None,
    strict_vad: bool | None = None,
    vad_config: VADConfig | None = None,
) -> Iterator[Segment]:
    """Transcribe a file synchronously, yielding segments as they are produced.

    This is the streaming counterpart to :func:`transcribe`. It accepts the
    same configuration and overrides but returns a generator of ``Segment``
    objects rather than a single ``TranscriptionResult``. With a lazily-decoding
    backend (faster-whisper) segments arrive incrementally; other backends yield
    once decoding completes. ``output_format`` is not accepted because streaming
    emits raw segments, not a formatted document.

    Args:
        path: Path to the audio/video file to transcribe.
        options: Transcription options. If None, loads defaults from config.
        config: Application configuration. If None, loads via load_config().
        cancellation_token: Optional token checked between segments.
        backend: Optional backend override (enum or string).
        model_size: Optional model-size override (enum or string).
        language: Optional language override.
        backend_preference: Optional automatic backend selection preference.
        strict_vad: Optional VAD failure behavior override.
        vad_config: Optional VAD configuration override.

    Yields:
        Segment: Each transcribed segment, in order.

    Raises:
        AudioCoreError: Base exception for all AudioCore errors.

    Example:
        >>> from audiocore import stream_transcribe
        >>> for segment in stream_transcribe("audio.mp3"):
        ...     print(f"[{segment.start_time:.2f}s] {segment.text}")
    """
    from audiocore.config import load_config

    if config is None:
        config = load_config()
    config = _apply_vad_config(config, vad_config)

    options = _resolve_options(
        config,
        options,
        backend=backend,
        model_size=model_size,
        language=language,
        backend_preference=backend_preference,
        strict_vad=strict_vad,
    )

    pipeline = Pipeline(config=config)
    yield from pipeline.stream_transcribe(
        path=path,
        options=options,
        cancellation_token=cancellation_token,
    )


async def async_transcribe(
    path: str | Path | list[str | Path] | tuple[str | Path, ...],
    options: TranscriptionOptions | None = None,
    config: AppConfig | None = None,
    progress_callback: ProgressCallback | None = None,
    cancellation_token: CancellationToken | None = None,
    max_workers: int = 4,
    *,
    backend: BackendType | str | None = None,
    model_size: ModelSize | str | None = None,
    language: str | None = None,
    output_format: OutputFormat | str | None = None,
    backend_preference: SelectionPolicy | str | None = None,
    strict_vad: bool | None = None,
    vad_config: VADConfig | None = None,
) -> TranscriptionResult | list[FileResult]:
    """Transcribe an audio/video file asynchronously.

    This function provides an async API for non-blocking transcription.
    It runs the synchronous transcribe() in a thread pool, allowing
    the event loop to remain responsive. Passing a list or tuple of paths
    enables concurrent batch transcription.

    Args:
        path: Path to the audio/video file to transcribe.
        options: Transcription options. If None, loads defaults from config
            or uses TranscriptionOptions() defaults.
        config: Application configuration. If None, loads from
            environment/TOML/defaults via load_config().
        progress_callback: Optional callback for progress notifications.
            Called from background thread, so callbacks should be thread-safe.
        cancellation_token: Optional token for cancellation support.
        max_workers: Maximum thread workers for async or batch processing.
        backend: Optional backend override (enum or string).
        model_size: Optional model-size override (enum or string).
        language: Optional language override.
        output_format: Optional output-format override (enum or string).
        backend_preference: Optional automatic backend selection preference.
        strict_vad: Optional VAD failure behavior override.
        vad_config: Optional VAD configuration override.

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

        >>> # Batch transcription
        >>> results = await async_transcribe(["audio1.mp3", "audio2.mp3"], max_workers=2)
    """
    # Create a CancellationToken if none provided so cancellation always propagates
    from audiocore.pipeline.cancellation import CancellationToken

    if cancellation_token is None:
        cancellation_token = CancellationToken()

    try:
        if _is_batch_path(path):
            return await _async_transcribe_batch(
                path,
                options,
                config,
                progress_callback,
                cancellation_token,
                max_workers,
                backend=backend,
                model_size=model_size,
                language=language,
                output_format=output_format,
                backend_preference=backend_preference,
                strict_vad=strict_vad,
                vad_config=vad_config,
            )

        return await _async_transcribe_single(
            path,
            options,
            config,
            progress_callback,
            cancellation_token,
            max_workers,
            backend=backend,
            model_size=model_size,
            language=language,
            output_format=output_format,
            backend_preference=backend_preference,
            strict_vad=strict_vad,
            vad_config=vad_config,
        )
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
        # Wrap unexpected exceptions, preserving original type in context
        raise AudioCoreError(
            f"Unexpected error during transcription: {e}",
            context={"path": str(path), "original_type": type(e).__name__},
        ) from e


async def _async_transcribe_single(
    path: str | Path,
    options: TranscriptionOptions | None,
    config: AppConfig | None,
    progress_callback: ProgressCallback | None,
    cancellation_token: CancellationToken,
    max_workers: int,
    *,
    backend: BackendType | str | None,
    model_size: ModelSize | str | None,
    language: str | None,
    output_format: OutputFormat | str | None,
    backend_preference: SelectionPolicy | str | None,
    strict_vad: bool | None,
    vad_config: VADConfig | None,
) -> TranscriptionResult:
    """Run the synchronous transcribe() in the shared executor thread pool."""
    loop = asyncio.get_running_loop()
    sync_call = partial(
        transcribe,
        path=path,
        options=options,
        config=config,
        progress_callback=progress_callback,
        cancellation_token=cancellation_token,
        backend=backend,
        model_size=model_size,
        language=language,
        output_format=output_format,
        backend_preference=backend_preference,
        strict_vad=strict_vad,
        vad_config=vad_config,
    )
    return await loop.run_in_executor(_get_executor(max_workers=max_workers), sync_call)


async def _async_transcribe_batch(
    batch_path: list[str | Path] | tuple[str | Path, ...],
    options: TranscriptionOptions | None,
    config: AppConfig | None,
    progress_callback: ProgressCallback | None,
    cancellation_token: CancellationToken,
    max_workers: int,
    *,
    backend: BackendType | str | None,
    model_size: ModelSize | str | None,
    language: str | None,
    output_format: OutputFormat | str | None,
    backend_preference: SelectionPolicy | str | None,
    strict_vad: bool | None,
    vad_config: VADConfig | None,
) -> list[FileResult]:
    """Resolve options and run concurrent batch transcription for a path list."""
    from audiocore.config import load_config
    from audiocore.parallel.files import transcribe_files_concurrent
    from audiocore.pipeline.progress import PipelineStage

    if config is None:
        config = load_config()
    config = _apply_vad_config(config, vad_config)

    effective_options = _resolve_options(
        config,
        options,
        backend=backend,
        model_size=model_size,
        language=language,
        output_format=output_format,
        backend_preference=backend_preference,
        strict_vad=strict_vad,
    )

    batch_progress_callback = None
    if progress_callback is not None:

        def batch_progress_callback(completed: int, total: int, current_path: Path) -> None:
            progress = completed / total if total else 1.0
            progress_callback(
                PipelineStage.TRANSCRIBING,
                progress,
                f"Processed {current_path}",
            )

    return await transcribe_files_concurrent(
        files=[Path(file_path) for file_path in batch_path],
        options=effective_options,
        max_workers=max_workers,
        config=config,
        progress_callback=batch_progress_callback,
        cancellation_token=cancellation_token,
    )


def shutdown_executor() -> None:
    """Shutdown the thread pool executor for async operations.

    Call this to clean up resources when done with async_transcribe.
    After calling this, async_transcribe will create a new executor.
    """
    global _executor, _executor_max_workers
    with _executor_lock:
        while _retired_executors:
            _retired_executors.pop().shutdown(wait=True)
        if _executor is not None:
            _executor.shutdown(wait=True)
            _executor = None
            _executor_max_workers = 0


__all__ = [
    "transcribe",
    "async_transcribe",
    "shutdown_executor",
]
