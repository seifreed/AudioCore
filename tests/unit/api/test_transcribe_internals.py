"""Unit tests for audiocore.api.transcribe internal helpers and branches.

Covers the public-API override parsers, option resolution, the shared
executor lifecycle, streaming, and the async cancellation/batch paths.
"""

from __future__ import annotations

import asyncio
import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audiocore.config import AppConfig
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType, ModelSize, OutputFormat, SelectionPolicy
from audiocore.vad.config import VADConfig

# audiocore.api.transcribe is shadowed by the transcribe() function exported from
# audiocore.api, so the module is loaded explicitly via importlib.
api = importlib.import_module("audiocore.api.transcribe")


class TestOverrideParsers:
    """The public-API override parsers coerce strings and reject bad types."""

    def test_parse_backend_rejects_bad_type(self) -> None:
        with pytest.raises(TypeError, match="backend must be"):
            api._parse_backend(123)

    def test_parse_model_size_accepts_string_and_rejects_bad_type(self) -> None:
        assert api._parse_model_size("small") == ModelSize.SMALL
        with pytest.raises(TypeError, match="model_size must be"):
            api._parse_model_size(123)

    def test_parse_output_format_rejects_bad_type(self) -> None:
        with pytest.raises(TypeError, match="output_format must be"):
            api._parse_output_format(123)

    def test_parse_backend_preference_accepts_string_and_rejects_bad_type(self) -> None:
        assert api._parse_backend_preference("prefer_local") == SelectionPolicy.PREFER_LOCAL
        with pytest.raises(TypeError, match="backend_preference must be"):
            api._parse_backend_preference(123)

    def test_parse_strict_vad_rejects_bad_type(self) -> None:
        with pytest.raises(TypeError, match="strict_vad must be"):
            api._parse_strict_vad("yes")

    def test_parse_vad_config_rejects_bad_type(self) -> None:
        with pytest.raises(TypeError, match="vad_config must be"):
            api._parse_vad_config(object())


class TestResolveOptions:
    """_resolve_options merges overrides onto provided options."""

    def test_overrides_applied_to_existing_options(self) -> None:
        resolved = api._resolve_options(
            AppConfig(),
            TranscriptionOptions(),
            backend="openai",
            model_size="small",
            language="en",
            output_format="srt",
            backend_preference="prefer_local",
            strict_vad=True,
        )
        assert resolved.backend == BackendType.OPENAI
        assert resolved.model_size == ModelSize.SMALL
        assert resolved.language == "en"
        assert resolved.output_format == OutputFormat.SRT
        assert resolved.backend_preference == SelectionPolicy.PREFER_LOCAL
        assert resolved.strict_vad is True

    def test_non_string_language_rejected(self) -> None:
        with pytest.raises(TypeError, match="language must be"):
            api._resolve_options(AppConfig(), None, language=123)

    def test_existing_options_unchanged_without_overrides(self) -> None:
        options = TranscriptionOptions(language="fr")
        resolved = api._resolve_options(AppConfig(), options)
        assert resolved is options

    def test_apply_vad_config_copies_when_provided(self) -> None:
        vad = VADConfig(speech_threshold=0.7)
        updated = api._apply_vad_config(AppConfig(), vad)
        assert updated.vad.speech_threshold == 0.7

    def test_parse_vad_config_passes_through_instance(self) -> None:
        vad = VADConfig()
        assert api._parse_vad_config(vad) is vad


class TestExecutorLifecycle:
    """The shared executor is created on demand, grows, and shuts down."""

    def _save(self):
        return (api._executor, api._executor_max_workers, list(api._retired_executors))

    def _restore(self, saved) -> None:
        api._executor, api._executor_max_workers, retired = saved
        api._retired_executors[:] = retired

    def test_rejects_invalid_max_workers(self) -> None:
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            api._get_executor(0)

    def test_grows_and_retires_smaller_executor(self) -> None:
        saved = self._save()
        try:
            api._executor = None
            api._executor_max_workers = 0
            api._retired_executors.clear()

            first = api._get_executor(2)
            grown = api._get_executor(8)

            assert grown is not first
            assert first in api._retired_executors
            assert api._executor_max_workers == 8
        finally:
            for ex in (api._executor, *api._retired_executors):
                if ex is not None:
                    ex.shutdown(wait=False)
            self._restore(saved)

    def test_smaller_request_returns_existing_executor(self) -> None:
        saved = self._save()
        try:
            api._executor = None
            api._executor_max_workers = 0
            api._retired_executors.clear()

            big = api._get_executor(8)
            same = api._get_executor(2)  # smaller -> no new executor

            assert same is big
            assert api._retired_executors == []
        finally:
            if api._executor is not None:
                api._executor.shutdown(wait=False)
            self._restore(saved)

    def test_cleanup_executor_with_no_executor_exits(self) -> None:
        saved = self._save()
        try:
            api._executor = None
            api._executor_max_workers = 0
            api._retired_executors.clear()

            api._cleanup_executor()  # nothing to shut down

            assert api._executor is None
        finally:
            self._restore(saved)

    def test_shutdown_executor_shuts_down_active_executor(self) -> None:
        saved = self._save()
        try:
            api._executor = ThreadPoolExecutor(max_workers=1)
            api._executor_max_workers = 1
            api._retired_executors.clear()

            api.shutdown_executor()

            assert api._executor is None
            assert api._executor_max_workers == 0
        finally:
            self._restore(saved)

    def test_cleanup_executor_shuts_everything_down(self) -> None:
        saved = self._save()
        try:
            api._retired_executors[:] = [ThreadPoolExecutor(max_workers=1)]
            api._executor = ThreadPoolExecutor(max_workers=1)
            api._executor_max_workers = 1

            api._cleanup_executor()

            assert api._executor is None
            assert api._executor_max_workers == 0
            assert api._retired_executors == []
        finally:
            self._restore(saved)

    def test_shutdown_executor_with_no_executor_is_noop(self) -> None:
        saved = self._save()
        try:
            api._executor = None
            api._executor_max_workers = 0
            api._retired_executors[:] = [ThreadPoolExecutor(max_workers=1)]

            api.shutdown_executor()

            assert api._executor is None
            assert api._retired_executors == []
        finally:
            self._restore(saved)


def _result() -> TranscriptionResult:
    return TranscriptionResult(
        segments=[Segment(start_time=0.0, end_time=1.0, text="hi")],
        media_info=MediaInfo(duration=1.0, format="wav"),
        config_used=TranscriptionOptions(),
        processing_time_seconds=0.1,
        backend_used=BackendType.OPENAI,
    )


class TestStreamTranscribe:
    """stream_transcribe resolves config/options and streams from the pipeline."""

    def test_streams_segments(self, tmp_path: Path) -> None:
        pipeline = MagicMock()
        pipeline.stream_transcribe.return_value = iter(
            [Segment(start_time=0.0, end_time=1.0, text="a")]
        )
        with patch("audiocore.api.transcribe.Pipeline", return_value=pipeline):
            segments = list(api.stream_transcribe("audio.mp3", config=AppConfig()))
        assert [s.text for s in segments] == ["a"]

    def test_loads_config_when_omitted(self) -> None:
        pipeline = MagicMock()
        pipeline.stream_transcribe.return_value = iter([])
        with (
            patch("audiocore.config.load_config", return_value=AppConfig()) as load,
            patch("audiocore.api.transcribe.Pipeline", return_value=pipeline),
        ):
            list(api.stream_transcribe("audio.mp3"))
        load.assert_called_once()


class TestAsyncTranscribePaths:
    """async_transcribe honors a supplied token, cancellation, and batch paths."""

    def test_uses_supplied_cancellation_token(self) -> None:
        from audiocore.pipeline.cancellation import CancellationToken

        token = CancellationToken()
        with patch(
            "audiocore.api.transcribe._async_transcribe_single",
            return_value=_result(),
        ) as single:

            async def _run():
                return await api.async_transcribe("audio.mp3", cancellation_token=token)

            asyncio.run(_run())

        assert single.call_args.args[4] is token

    def test_cancellation_signals_token_and_reraises(self) -> None:
        from audiocore.pipeline.cancellation import CancellationToken

        token = CancellationToken()

        async def _raise_cancel(*args, **kwargs):
            raise asyncio.CancelledError()

        with patch(
            "audiocore.api.transcribe._async_transcribe_single",
            side_effect=_raise_cancel,
        ):

            async def _run():
                await api.async_transcribe("audio.mp3", cancellation_token=token)

            with pytest.raises(asyncio.CancelledError):
                asyncio.run(_run())

        assert token.is_cancelled

    def test_batch_path_loads_config_and_reports_progress(self, tmp_path: Path) -> None:
        files = [tmp_path / "a.wav", tmp_path / "b.wav"]
        for f in files:
            f.write_bytes(b"x")
        progress_events: list[tuple] = []

        async def _fake_concurrent(
            *, files, options, max_workers, config, progress_callback, cancellation_token
        ):
            # Exercise the wrapped progress callback the batch path builds.
            if progress_callback is not None:
                progress_callback(1, 2, files[0])
            return [FileResultStub(f) for f in files]

        class FileResultStub:
            def __init__(self, path):
                self.path = path
                self.success = True

        with (
            patch("audiocore.config.load_config", return_value=AppConfig()) as load,
            patch(
                "audiocore.parallel.files.transcribe_files_concurrent",
                side_effect=_fake_concurrent,
            ),
        ):

            async def _run():
                return await api.async_transcribe(
                    [str(f) for f in files],
                    progress_callback=lambda stage, p, msg: progress_events.append((stage, p, msg)),
                )

            results = asyncio.run(_run())

        load.assert_called_once()
        assert len(results) == 2
        assert progress_events  # the batch progress wrapper fired

    def test_batch_path_with_config_and_no_progress(self, tmp_path: Path) -> None:
        files = [tmp_path / "a.wav", tmp_path / "b.wav"]
        for f in files:
            f.write_bytes(b"x")

        async def _fake_concurrent(
            *, files, options, max_workers, config, progress_callback, cancellation_token
        ):
            assert progress_callback is None  # no wrapper built without a callback
            return list(files)

        with (
            patch("audiocore.config.load_config") as load,
            patch(
                "audiocore.parallel.files.transcribe_files_concurrent",
                side_effect=_fake_concurrent,
            ),
        ):

            async def _run():
                return await api.async_transcribe([str(f) for f in files], config=AppConfig())

            results = asyncio.run(_run())

        load.assert_not_called()  # config supplied -> no load_config
        assert len(results) == 2
