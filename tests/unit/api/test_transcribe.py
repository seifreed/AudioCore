"""
Tests for transcribe and async_transcribe functions.

This module tests the public API transcribe functions with mocked Pipeline.
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiocore import (
    AudioCoreError,
    BackendType,
    MediaFormatError,
    OutputFormat,
    TranscriptionOptions,
    TranscriptionResult,
    async_transcribe,
    transcribe,
)
from audiocore.config import AppConfig
from audiocore.models import MediaInfo
from audiocore.models.segment import Segment
from audiocore.parallel import FileResult
from audiocore.types import ModelSize


class TestSyncTranscribe:
    """Tests for synchronous transcribe function."""

    def test_transcribe_calls_pipeline(self, tmp_path: Path):
        """Verify transcribe creates Pipeline and calls transcribe."""
        # Create mock result
        mock_result = TranscriptionResult(
            segments=[
                Segment(start_time=0.0, end_time=5.0, text="Hello world"),
            ],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        # Mock Pipeline
        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            # Call transcribe
            result = transcribe("audio.mp3")

            # Verify Pipeline was created with config
            mock_pipeline_class.assert_called_once()

            # Verify transcribe was called
            mock_pipeline.transcribe.assert_called_once()

            # Verify result
            assert result == mock_result
            assert result.segments[0].text == "Hello world"

    def test_transcribe_with_options(self, tmp_path: Path):
        """Verify transcribe passes options correctly."""
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(backend=BackendType.OPENAI),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            options = TranscriptionOptions(backend=BackendType.OPENAI)
            result = transcribe("audio.mp3", options=options)

            # Verify options were passed
            call_kwargs = mock_pipeline.transcribe.call_args
            assert call_kwargs[1]["options"] == options or call_kwargs[0][1] == options
            assert result.segments[0].text == "Test"

    def test_transcribe_raises_audiocore_errors(self):
        """Verify AudioCoreError exceptions are re-raised."""
        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.side_effect = MediaFormatError(
                "Unsupported format",
                context={"format": "xyz"},
            )
            mock_pipeline_class.return_value = mock_pipeline

            with pytest.raises(MediaFormatError) as exc_info:
                transcribe("audio.xyz")

            assert "Unsupported format" in str(exc_info.value)

    def test_transcribe_with_config(self):
        """Verify transcribe uses provided config."""
        from audiocore.config import AppConfig

        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        config = AppConfig()  # Use default config

        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            result = transcribe("audio.mp3", config=config)

            # Verify config was passed to Pipeline
            mock_pipeline_class.assert_called_once()
            assert result.segments[0].text == "Test"

    def test_transcribe_default_options_do_not_mask_faster_whisper_config_model(self):
        """Regression: public API defaults must not override nested faster-whisper model."""
        from audiocore.config import AppConfig
        from audiocore.config.faster_whisper_config import FasterWhisperConfig
        from audiocore.types import ModelSize

        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.FASTER_WHISPER,
        )
        config = AppConfig(
            backend=BackendType.FASTER_WHISPER,
            faster_whisper=FasterWhisperConfig(model_size=ModelSize.TINY),
        )

        with (
            patch("audiocore.config.load_config", return_value=config),
            patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class,
        ):
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            transcribe("audio.mp3")

        used_options = mock_pipeline.transcribe.call_args[1]["options"]
        assert "model_size" not in used_options.model_fields_set

    def test_transcribe_accepts_documented_keyword_options(self):
        """Regression: README-documented convenience keywords are part of the public API."""
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            transcribe(
                "audio.mp3",
                config=AppConfig(),
                backend=BackendType.OPENAI,
                language="es",
                output_format=OutputFormat.SRT,
            )

        used_options = mock_pipeline.transcribe.call_args[1]["options"]
        assert used_options.backend == BackendType.OPENAI
        assert used_options.language == "es"
        assert used_options.output_format == OutputFormat.SRT

    def test_transcribe_string_keyword_options_merge_with_existing_options(self):
        """Keyword overrides should be friendly strings and preserve untouched options."""
        base_options = TranscriptionOptions(
            backend=BackendType.FASTER_WHISPER,
            model_size=ModelSize.TINY,
        )
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=base_options,
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            transcribe(
                "audio.mp3",
                options=base_options,
                config=AppConfig(),
                backend="openai",
                output_format="json",
            )

        used_options = mock_pipeline.transcribe.call_args[1]["options"]
        assert used_options.backend == BackendType.OPENAI
        assert used_options.output_format == OutputFormat.JSON
        assert used_options.model_size == ModelSize.TINY
        assert "model_size" in used_options.model_fields_set


class TestAsyncTranscribe:
    """Tests for asynchronous async_transcribe function."""

    def test_async_transcribe_returns_result(self):
        """Verify async_transcribe returns TranscriptionResult."""

        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Async test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.return_value = mock_result

            # Run async function
            result = asyncio.run(async_transcribe("audio.mp3"))

            # Verify result
            assert result == mock_result
            assert result.segments[0].text == "Async test"

    def test_async_transcribe_with_options(self):
        """Verify async_transcribe passes options correctly."""
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Options test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(backend=BackendType.OPENAI),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.return_value = mock_result

            options = TranscriptionOptions(backend=BackendType.OPENAI)
            result = asyncio.run(async_transcribe("audio.mp3", options=options))

            # Verify options were passed
            assert mock_sync_transcribe.called
            assert result.segments[0].text == "Options test"

    def test_async_transcribe_raises_audiocore_errors(self):
        """Verify AudioCoreError exceptions are re-raised."""
        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.side_effect = MediaFormatError(
                "Unsupported format",
                context={"format": "xyz"},
            )

            async def run_test():
                with pytest.raises(MediaFormatError) as exc_info:
                    await async_transcribe("audio.xyz")
                assert "Unsupported format" in str(exc_info.value)

            asyncio.run(run_test())

    def test_async_transcribe_concurrent_execution(self):
        """Test that async_transcribe supports concurrent execution."""
        mock_result_1 = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="File 1")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )
        mock_result_2 = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="File 2")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        call_count = 0

        def mock_transcribe_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_result_1
            return mock_result_2

        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.side_effect = mock_transcribe_side_effect

            async def run_concurrent():
                # Run two transcribe calls concurrently
                results = await asyncio.gather(
                    async_transcribe("audio1.mp3"),
                    async_transcribe("audio2.mp3"),
                )
                return results

            results = asyncio.run(run_concurrent())

            # Verify both results returned (order may vary due to concurrent execution)
            assert len(results) == 2
            texts = [r.segments[0].text for r in results]
            assert "File 1" in texts
            assert "File 2" in texts

    def test_async_transcribe_wraps_unexpected_errors(self):
        """Verify unexpected exceptions are wrapped in AudioCoreError."""

        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            # Simulate an unexpected error (not AudioCoreError)
            mock_sync_transcribe.side_effect = RuntimeError("Unexpected error")

            async def run_test():
                with pytest.raises(AudioCoreError) as exc_info:
                    await async_transcribe("audio.mp3")
                assert "Unexpected error" in str(exc_info.value)

            asyncio.run(run_test())

    def test_async_transcribe_accepts_documented_keyword_options(self):
        """Regression: async_transcribe must mirror transcribe convenience options."""
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Async test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.return_value = mock_result

            result = asyncio.run(
                async_transcribe(
                    "audio.mp3",
                    config=AppConfig(),
                    backend=BackendType.OPENAI,
                    output_format=OutputFormat.JSON,
                    max_workers=1,
                )
            )

        assert result == mock_result
        used_kwargs = mock_sync_transcribe.call_args.kwargs
        assert used_kwargs["backend"] == BackendType.OPENAI
        assert used_kwargs["output_format"] == OutputFormat.JSON

    def test_async_transcribe_accepts_documented_file_list_batch(self):
        """Regression: README-documented async batch API should process file lists."""
        files = [Path("audio1.mp3"), Path("audio2.mp3")]
        config = AppConfig()
        batch_results = [
            FileResult(path=files[0], success=True, result=None, error=None),
            FileResult(path=files[1], success=True, result=None, error=None),
        ]

        async def fake_transcribe_files_concurrent(*args, **kwargs):
            return batch_results

        with patch(
            "audiocore.parallel.files.transcribe_files_concurrent",
            side_effect=fake_transcribe_files_concurrent,
        ) as mock_batch:
            results = asyncio.run(
                async_transcribe(
                    files,
                    config=config,
                    backend=BackendType.FASTER_WHISPER,
                    max_workers=2,
                )
            )

        assert results == batch_results
        used_kwargs = mock_batch.call_args.kwargs
        assert used_kwargs["files"] == files
        assert used_kwargs["config"] is config
        assert used_kwargs["max_workers"] == 2
        assert used_kwargs["options"].backend == BackendType.FASTER_WHISPER


class TestShutdownExecutor:
    """Tests for executor shutdown."""

    def test_shutdown_executor(self):
        """Verify shutdown_executor cleans up thread pool."""
        from audiocore.api.transcribe import shutdown_executor

        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Test")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        # Create executor by calling async_transcribe
        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.return_value = mock_result
            asyncio.run(async_transcribe("audio.mp3"))

        # Shutdown executor
        shutdown_executor()

        # Re-create executor (second call)
        with patch("audiocore.api.transcribe.transcribe") as mock_sync_transcribe:
            mock_sync_transcribe.return_value = mock_result
            asyncio.run(async_transcribe("audio.mp3"))

        # Clean up
        shutdown_executor()

    def test_shutdown_executor_sets_none(self):
        """Verify shutdown_executor sets _executor to None."""
        import importlib

        # Get the actual transcribe module, not the lazy-loaded function

        transcribe_module = importlib.import_module("audiocore.api.transcribe")

        # First ensure executor is None (clean state)
        transcribe_module._executor = None

        # Call _get_executor to create one
        executor = transcribe_module._get_executor()
        assert executor is not None
        assert transcribe_module._executor is not None

        # Shutdown
        transcribe_module.shutdown_executor()

        # Verify executor is None
        assert transcribe_module._executor is None

    def test_get_executor_thread_safety(self):
        """Regression: _get_executor must be thread-safe.

        Previously, _get_executor() had no lock, so concurrent calls could
        create multiple executors and leak all but the last.
        """
        import importlib
        import threading

        transcribe_module = importlib.import_module("audiocore.api.transcribe")

        # Reset executor state
        transcribe_module._executor = None

        executors = []
        errors = []

        def get_executor():
            try:
                ex = transcribe_module._get_executor()
                executors.append(id(ex))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_executor) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent _get_executor: {errors}"
        # All threads must get the same executor instance
        executor_count = len(set(executors))
        assert executor_count == 1, f"Expected one executor instance, got {executor_count}"

        # Clean up
        transcribe_module.shutdown_executor()


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_transcribe_loads_config_automatically(self):
        """Verify transcribe loads config when not provided."""
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Auto config")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            # Call transcribe without config
            result = transcribe("audio.mp3")

            # Verify config was loaded (Pipeline was created)
            mock_pipeline_class.assert_called_once()
            assert result.segments[0].text == "Auto config"

    def test_transcribe_uses_default_options(self):
        """Verify transcribe creates default options when not provided."""
        mock_result = TranscriptionResult(
            segments=[Segment(start_time=0.0, end_time=5.0, text="Default options")],
            media_info=MediaInfo(duration=5.0, format="wav"),
            config_used=TranscriptionOptions(),
            processing_time_seconds=1.0,
            backend_used=BackendType.OPENAI,
        )

        with patch("audiocore.api.transcribe.Pipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.transcribe.return_value = mock_result
            mock_pipeline_class.return_value = mock_pipeline

            # Call transcribe without options
            result = transcribe("audio.mp3")

            # Verify default options were used (TranscriptionOptions())
            mock_pipeline.transcribe.assert_called_once()
            assert result.segments[0].text == "Default options"
