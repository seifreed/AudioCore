"""Unit tests for FasterWhisperBackend implementation.

Tests cover:
- Backend type and name
- Availability checking
- Model options listing
- Lazy model loading
- Device auto-detection
- Transcription with mocked model
- Error handling (file not found, transcription errors)
- Configuration parameter passing
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
from audiocore.config import AppConfig
from audiocore.config.faster_whisper_config import ComputeType, FasterWhisperConfig
from audiocore.errors import BackendUnavailableError, TranscriptionError
from audiocore.models import TranscriptionOptions
from audiocore.types import BackendType, ModelSize


class TestFasterWhisperBackendBasics:
    """Test basic backend properties and methods."""

    def test_backend_type_returns_faster_whisper(self) -> None:
        """Backend type should return FASTER_WHISPER."""
        backend = FasterWhisperBackend()
        assert backend.backend_type == BackendType.FASTER_WHISPER

    def test_get_name_returns_faster_whisper_local(self) -> None:
        """get_name() should return 'Faster-Whisper (local)'."""
        backend = FasterWhisperBackend()
        assert backend.get_name() == "Faster-Whisper (local)"

    @patch.dict("sys.modules", {"ctranslate2": MagicMock(), "faster_whisper": MagicMock()})
    def test_is_available_returns_true_when_installed(self) -> None:
        """is_available() should return True when faster-whisper is installed."""
        backend = FasterWhisperBackend()
        assert backend.is_available() is True

    def test_is_available_returns_false_when_not_installed(self) -> None:
        """is_available() should return False when faster-whisper is not installed."""
        backend = FasterWhisperBackend()
        # A None entry in sys.modules makes `import x` raise ImportError, without
        # globally overriding __import__ (which would also break coverage tracing).
        with patch.dict("sys.modules", {"ctranslate2": None, "faster_whisper": None}):
            result = backend.is_available()
        assert result is False

    def test_get_model_options_returns_list_of_models(self) -> None:
        """get_model_options() should return list of model sizes."""
        backend = FasterWhisperBackend()
        models = backend.get_model_options()
        expected = ["tiny", "base", "small", "medium", "large", "large-v3", "large-v3-turbo"]
        assert models == expected


class TestFasterWhisperBackendConfig:
    """Test configuration handling."""

    def test_init_with_default_config(self) -> None:
        """Backend should use default config when none provided."""
        backend = FasterWhisperBackend()
        assert backend.config.model_size == ModelSize.BASE
        assert backend.config.device is None
        assert backend.config.compute_type == ComputeType.DEFAULT

    def test_init_with_custom_config(self) -> None:
        """Backend should use provided config."""
        config = FasterWhisperConfig(
            model_size=ModelSize.SMALL,
            device="cuda",
            compute_type=ComputeType.INT8,
            beam_size=10,
            best_of=15,  # best_of must be >= beam_size
        )
        backend = FasterWhisperBackend(config=config)
        assert backend.config.model_size == ModelSize.SMALL
        assert backend.config.device == "cuda"
        assert backend.config.compute_type == ComputeType.INT8
        assert backend.config.beam_size == 10
        assert backend.config.best_of == 15


class TestFasterWhisperBackendDevice:
    """Test device selection."""

    @patch("audiocore.backends.faster_whisper.get_best_device")
    def test_get_device_auto_detects_when_none(self, mock_get_best: Mock) -> None:
        """_get_device should auto-detect when config.device is None."""
        mock_get_best.return_value = "cuda"
        backend = FasterWhisperBackend()
        device = backend._get_device()
        assert device == "cuda"
        mock_get_best.assert_called_once()

    def test_get_device_uses_config_value_when_specified(self) -> None:
        """_get_device should use config.device when specified."""
        config = FasterWhisperConfig(device="cpu")
        backend = FasterWhisperBackend(config=config)
        device = backend._get_device()
        assert device == "cpu"


class TestFasterWhisperBackendTranscribe:
    """Test transcription functionality."""

    def test_transcribe_raises_error_when_file_not_found(self) -> None:
        """transcribe should raise InvalidInputError when file not found."""
        backend = FasterWhisperBackend()
        options = TranscriptionOptions()

        from audiocore.errors import InvalidInputError

        with pytest.raises(InvalidInputError) as exc_info:
            backend.transcribe("/nonexistent/audio.mp3", options)

        assert "not found" in str(exc_info.value)
        file_path = exc_info.value.context.get("file_path")
        assert file_path is not None
        assert Path(file_path) == Path("/nonexistent/audio.mp3")

    @patch("audiocore.backends.faster_whisper_backend.Path.exists")
    def test_transcribe_file_not_found_context(self, mock_exists: Mock) -> None:
        """transcribe error should have proper context."""
        mock_exists.return_value = False
        backend = FasterWhisperBackend()
        options = TranscriptionOptions()

        from audiocore.errors import InvalidInputError

        with pytest.raises(InvalidInputError) as exc_info:
            backend.transcribe("audio.mp3", options)

        error = exc_info.value
        assert error.context.get("file_path") == "audio.mp3"
        assert error.context.get("backend") == "faster_whisper"

    def test_transcribe_directory_raises_invalid_input_error(self, tmp_path: Path) -> None:
        """Existing directories should be rejected before loading a model."""
        from audiocore.errors import InvalidInputError

        audio_dir = tmp_path / "audio.mp3"
        audio_dir.mkdir()
        backend = FasterWhisperBackend()

        with (
            patch.object(backend, "_load_model") as mock_load_model,
            pytest.raises(InvalidInputError) as exc_info,
        ):
            backend.transcribe(audio_dir, TranscriptionOptions())

        assert "not a file" in str(exc_info.value)
        mock_load_model.assert_not_called()


class TestFasterWhisperBackendModelLoading:
    """Test lazy model loading."""

    def test_model_none_on_init(self) -> None:
        """Model should be None after initialization."""
        backend = FasterWhisperBackend()
        assert backend._model is None

    def test_load_model_raises_backend_unavailable_when_not_installed(self, tmp_path: Path) -> None:
        """is_available() should return False when faster-whisper is not importable."""
        backend = FasterWhisperBackend()
        # A None entry in sys.modules makes `import faster_whisper` raise ImportError,
        # without globally overriding __import__ (which would also break coverage tracing).
        with patch.dict("sys.modules", {"faster_whisper": None}):
            result = backend.is_available()
        assert result is False


class TestFasterWhisperBackendTranscription:
    """Test successful transcription with mocked model."""

    def test_transcribe_successful_transcription(self, tmp_path: Path) -> None:
        """transcribe should return TranscriptionResult on success."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock segment
        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.text = "Hello world"

        # Mock info
        mock_info = MagicMock()
        mock_info.duration = 5.0

        # Mock model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                config = FasterWhisperConfig(model_size=ModelSize.BASE, device="cpu")
                backend = FasterWhisperBackend(config=config)
                options = TranscriptionOptions()

                result = backend.transcribe(str(audio_file), options)

        # Verify result
        assert result.backend_used == BackendType.FASTER_WHISPER
        assert len(result.segments) == 1
        assert result.segments[0].text == "Hello world"
        assert result.media_info.duration == 5.0

    def test_transcribe_converts_multiple_segments(self, tmp_path: Path) -> None:
        """transcribe should convert all segments correctly."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock segments
        mock_segments = [
            MagicMock(start=0.0, end=2.0, text="First "),
            MagicMock(start=2.0, end=4.0, text="Second "),
            MagicMock(start=4.0, end=6.0, text="Third"),
        ]

        # Mock info
        mock_info = MagicMock()
        mock_info.duration = 6.0

        # Mock model
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (mock_segments, mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                backend = FasterWhisperBackend()
                options = TranscriptionOptions()
                result = backend.transcribe(str(audio_file), options)

        # Verify segments
        assert len(result.segments) == 3
        assert result.segments[0].text == "First"
        assert result.segments[1].text == "Second"
        assert result.segments[2].text == "Third"

    def test_transcribe_handles_transcription_error(self, tmp_path: Path) -> None:
        """transcribe should raise TranscriptionError on model error."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock model that raises error
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("Transcription failed")

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                backend = FasterWhisperBackend()
                options = TranscriptionOptions()

                with pytest.raises(TranscriptionError) as exc_info:
                    backend.transcribe(str(audio_file), options)

        error = exc_info.value
        assert "transcription failed" in error.message.lower()


class TestFasterWhisperBackendParameters:
    """Test configuration parameter passing."""

    def test_default_options_do_not_override_backend_config_model(self, tmp_path: Path) -> None:
        """Regression: TranscriptionOptions() default model must not mask backend config."""
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        mock_model = MagicMock()
        mock_segment = MagicMock(start=0.0, end=1.0, text="Test")
        mock_info = MagicMock(duration=1.0)
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        mock_whisper_class = MagicMock(return_value=mock_model)

        with patch.dict(
            sys.modules,
            {
                "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
            },
        ):
            config = FasterWhisperConfig(model_size=ModelSize.TINY, device="cpu")
            backend = FasterWhisperBackend(config=config)
            backend.transcribe(str(audio_file), TranscriptionOptions())

        call_args, call_kwargs = mock_whisper_class.call_args
        assert call_args[0] == "tiny"
        assert call_kwargs["download_root"] == str(backend._model_manager.cache_dir)

    def test_transcribe_uses_config_language(self, tmp_path: Path) -> None:
        """transcribe should pass language from config."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock model
        mock_model = MagicMock()
        mock_segment = MagicMock(start=0.0, end=1.0, text="Test")
        mock_info = MagicMock(duration=1.0)
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                config = FasterWhisperConfig(model_size=ModelSize.BASE, device="cpu", language="en")
                backend = FasterWhisperBackend(config=config)
                options = TranscriptionOptions()
                backend.transcribe(str(audio_file), options)

        # Verify language was passed
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("language") == "en"

    def test_transcribe_options_language_overrides_config(self, tmp_path: Path) -> None:
        """transcribe language option should override config."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock model
        mock_model = MagicMock()
        mock_segment = MagicMock(start=0.0, end=1.0, text="Test")
        mock_info = MagicMock(duration=1.0)
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                config = FasterWhisperConfig(model_size=ModelSize.BASE, device="cpu", language="es")
                backend = FasterWhisperBackend(config=config)
                options = TranscriptionOptions(language="fr")  # Override
                backend.transcribe(str(audio_file), options)

        # Verify options language was used
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("language") == "fr"

    def test_transcribe_uses_config_beam_size(self, tmp_path: Path) -> None:
        """transcribe should pass beam_size from config."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock model
        mock_model = MagicMock()
        mock_segment = MagicMock(start=0.0, end=1.0, text="Test")
        mock_info = MagicMock(duration=1.0)
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                config = FasterWhisperConfig(
                    model_size=ModelSize.BASE, device="cpu", beam_size=10, best_of=15
                )
                backend = FasterWhisperBackend(config=config)
                options = TranscriptionOptions()
                backend.transcribe(str(audio_file), options)

        # Verify beam_size was passed
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("beam_size") == 10
        assert call_kwargs.get("best_of") == 15

    def test_transcribe_uses_vad_filter(self, tmp_path: Path) -> None:
        """transcribe should pass vad_filter from config."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock model
        mock_model = MagicMock()
        mock_segment = MagicMock(start=0.0, end=1.0, text="Test")
        mock_info = MagicMock(duration=1.0)
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                config = FasterWhisperConfig(
                    model_size=ModelSize.BASE, device="cpu", vad_filter=True
                )
                backend = FasterWhisperBackend(config=config)
                options = TranscriptionOptions()
                backend.transcribe(str(audio_file), options)

        # Verify vad_filter was passed
        call_kwargs = mock_model.transcribe.call_args[1]
        assert call_kwargs.get("vad_filter") is True


class TestFasterWhisperBackendEdgeCases:
    """Test edge cases and error handling."""

    def test_transcribe_handles_zero_duration(self, tmp_path: Path) -> None:
        """transcribe should handle files with zero duration (uses minimum)."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock segments
        mock_segment = MagicMock(start=0.0, end=0.0, text="")
        mock_info = MagicMock(duration=0.0)
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                backend = FasterWhisperBackend()
                options = TranscriptionOptions()
                result = backend.transcribe(str(audio_file), options)

        # Verify result - zero duration should use minimum 0.01
        assert result.media_info.duration == 0.01  # Minimum duration fallback
        assert len(result.segments) == 1

    def test_transcribe_handles_empty_segments(self, tmp_path: Path) -> None:
        """transcribe should handle files with no speech."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock empty segments
        mock_info = MagicMock(duration=5.0)
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                backend = FasterWhisperBackend()
                options = TranscriptionOptions()
                result = backend.transcribe(str(audio_file), options)

        # Verify result
        assert len(result.segments) == 0
        assert result.media_info.duration == 5.0

    def test_transcribe_strips_whitespace(self, tmp_path: Path) -> None:
        """transcribe should strip whitespace from segment text."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.touch()

        # Mock segment with whitespace
        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 5.0
        mock_segment.text = "  Hello world  "

        mock_info = MagicMock(duration=5.0)
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)

        # Mock ModelManager
        mock_manager = MagicMock()
        mock_manager.download_model.return_value = Path("/tmp/model")

        # Mock WhisperModel
        mock_whisper_class = MagicMock(return_value=mock_model)

        # Patch in correct scope
        with patch(
            "audiocore.backends.faster_whisper_backend.ModelManager",
            return_value=mock_manager,
        ):
            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": MagicMock(WhisperModel=mock_whisper_class),
                },
            ):
                backend = FasterWhisperBackend()
                options = TranscriptionOptions()
                result = backend.transcribe(str(audio_file), options)

        # Verify text was stripped
        assert result.segments[0].text == "Hello world"


def _fake_torch(*, cuda_available, raises_import=False):
    torch = types.ModuleType("torch")

    class _Cuda:
        def is_available(self):
            return cuda_available

    torch.cuda = _Cuda()
    return torch


class TestFasterWhisperGetDeviceBranches:
    """_get_device resolves every device string and fallback."""

    def test_appconfig_unwraps_to_faster_whisper_subconfig(self) -> None:
        backend = FasterWhisperBackend(config=AppConfig())
        assert isinstance(backend.config, FasterWhisperConfig)

    def test_unknown_device_falls_back_to_cpu(self) -> None:
        backend = FasterWhisperBackend()
        backend.config.device = "weird"
        assert backend._get_device() == "cpu"

    def test_mps_device_falls_back_to_cpu(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="mps"))
        assert backend._get_device() == "cpu"

    def test_cuda_device_used_when_available(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cuda"))
        with patch.dict(sys.modules, {"torch": _fake_torch(cuda_available=True)}):
            assert backend._get_device() == "cuda"

    def test_cuda_device_falls_back_when_unavailable(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cuda"))
        with patch.dict(sys.modules, {"torch": _fake_torch(cuda_available=False)}):
            assert backend._get_device() == "cpu"

    def test_cuda_device_falls_back_without_torch(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cuda"))
        with patch.dict(sys.modules, {"torch": None}):
            assert backend._get_device() == "cpu"


class TestFasterWhisperInstantiateModel:
    """Model instantiation import/construction error handling."""

    def test_instantiate_raises_backend_unavailable_without_package(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        with patch.dict(sys.modules, {"faster_whisper": None}):
            with pytest.raises(BackendUnavailableError):
                backend._instantiate_model("base")

    def test_instantiate_wraps_construction_error(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))

        def _boom(*args, **kwargs):
            raise RuntimeError("ct2 load failed")

        with patch.dict(sys.modules, {"faster_whisper": types.SimpleNamespace(WhisperModel=_boom)}):
            with pytest.raises(TranscriptionError, match="Failed to load faster-whisper model"):
                backend._instantiate_model("base")


class TestFasterWhisperLoadModelBranches:
    """_load_model caching, switching, and double-checked lock."""

    def test_switches_model_when_size_differs(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        backend._model = MagicMock(name="old-model")
        backend._loaded_model_size = "base"

        new_model = MagicMock(name="new-model")
        with patch.object(backend, "_instantiate_model", return_value=new_model) as inst:
            result = backend._load_model(model_size="small")

        assert result is new_model
        assert backend._loaded_model_size == "small"
        inst.assert_called_once_with("small")

    def test_double_checked_lock_returns_cached_when_primed(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        cached = MagicMock(name="primed-model")

        class _PrimingLock:
            def __enter__(self):
                backend._model = cached
                backend._loaded_model_size = "base"
                return self

            def __exit__(self, *exc):
                return False

        backend._model_lock = _PrimingLock()
        with patch.object(backend, "_instantiate_model") as inst:
            result = backend._load_model(model_size="base")

        assert result is cached
        inst.assert_not_called()


class TestFasterWhisperTranscribeBranches:
    """transcribe / transcribe_stream model-size override and error handling."""

    def _audio(self, tmp_path: Path) -> Path:
        f = tmp_path / "clip.wav"
        f.touch()
        return f

    def test_transcribe_uses_options_model_size_override(self, tmp_path: Path) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        seg = MagicMock(start=0.0, end=1.0, text="hi", words=None)
        info = MagicMock(duration=1.0, language="en")
        model = MagicMock()
        model.transcribe.return_value = ([seg], info)

        with patch.object(backend, "_load_model", return_value=model) as load:
            options = TranscriptionOptions(model_size=ModelSize.SMALL)
            backend.transcribe(self._audio(tmp_path), options)

        load.assert_called_once_with(model_size=ModelSize.SMALL.value)

    def test_transcribe_reraises_backend_unavailable(self, tmp_path: Path) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        model = MagicMock()
        model.transcribe.side_effect = BackendUnavailableError("gone")

        with patch.object(backend, "_load_model", return_value=model):
            with pytest.raises(BackendUnavailableError):
                backend.transcribe(self._audio(tmp_path), TranscriptionOptions())

    def test_transcribe_wraps_generic_error(self, tmp_path: Path) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("decode error")

        with patch.object(backend, "_load_model", return_value=model):
            with pytest.raises(TranscriptionError, match="transcription failed"):
                backend.transcribe(self._audio(tmp_path), TranscriptionOptions())

    def test_stream_uses_options_model_size_override(self, tmp_path: Path) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        seg = MagicMock(start=0.0, end=1.0, words=None)
        seg.text = "hi"
        model = MagicMock()
        model.transcribe.return_value = ([seg], MagicMock())

        with patch.object(backend, "_load_model", return_value=model) as load:
            options = TranscriptionOptions(model_size=ModelSize.SMALL)
            list(backend.transcribe_stream(self._audio(tmp_path), options))

        load.assert_called_once_with(model_size=ModelSize.SMALL.value)

    def test_stream_reraises_backend_unavailable(self, tmp_path: Path) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        model = MagicMock()
        model.transcribe.side_effect = BackendUnavailableError("gone")

        with patch.object(backend, "_load_model", return_value=model):
            with pytest.raises(BackendUnavailableError):
                list(backend.transcribe_stream(self._audio(tmp_path), TranscriptionOptions()))

    def test_stream_wraps_generic_error(self, tmp_path: Path) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("decode error")

        with patch.object(backend, "_load_model", return_value=model):
            with pytest.raises(TranscriptionError, match="streaming transcription failed"):
                list(backend.transcribe_stream(self._audio(tmp_path), TranscriptionOptions()))

    def test_build_params_includes_initial_prompt(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(device="cpu"))
        backend.config.initial_prompt = "context here"
        params = backend._build_transcribe_params(TranscriptionOptions())
        assert params["initial_prompt"] == "context here"

    def test_auto_device_mps_detection_falls_back_to_cpu(self) -> None:
        backend = FasterWhisperBackend()  # config.device is None -> auto
        with patch("audiocore.backends.faster_whisper.get_best_device", return_value="mps"):
            assert backend._get_device() == "cpu"

    def test_load_model_quick_cache_hit_returns_without_lock(self) -> None:
        backend = FasterWhisperBackend(config=FasterWhisperConfig(model_size=ModelSize.BASE))
        cached = MagicMock(name="cached")
        backend._model = cached
        backend._loaded_model_size = "base"
        with patch.object(backend, "_instantiate_model") as inst:
            assert backend._load_model(model_size="base") is cached
        inst.assert_not_called()

    def test_extract_words_normalizes_timestamps_and_confidence(self) -> None:
        word = types.SimpleNamespace(word="hello", start=-0.2, end=0.5, probability=1.4)
        segment = types.SimpleNamespace(words=[word])

        result = FasterWhisperBackend._extract_words(segment)

        assert result is not None
        assert result[0].word == "hello"
        assert result[0].start_time == 0.0  # clamped from -0.2
        assert result[0].end_time == 0.5
        assert result[0].confidence == 1.0  # clamped from 1.4
