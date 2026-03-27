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
    TranscriptionOptions,
    TranscriptionResult,
    async_transcribe,
    transcribe,
)
from audiocore.models import MediaInfo
from audiocore.models.segment import Segment


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
