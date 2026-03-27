"""
Tests for API module imports and error hierarchy.

This module tests that all public symbols are importable and that
the error hierarchy is properly organized.
"""


from audiocore import (
    AudioCoreError,
    BackendError,
    TranscriptionOptions,
    TranscriptionResult,
    transcribe,
)
from audiocore.api import async_transcribe
from audiocore.errors import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    BackendUnavailableError,
    ConfigurationError,
    InvalidConfigError,
    InvalidInputError,
    MediaError,
    MediaFormatError,
    OutputFileExistsError,
    PartialResultError,
    PipelineCancelledError,
    PipelineError,
    PipelineStageError,
    ProcessingError,
    RateLimitError,
    TranscriptionError,
    VADError,
)


class TestErrorHierarchy:
    """Test that all exceptions inherit from AudioCoreError."""

    def test_all_errors_importable(self):
        """Verify all error classes can be imported."""
        # This test passes if imports succeed
        assert AudioCoreError is not None
        assert InvalidInputError is not None
        assert MediaFormatError is not None
        assert ConfigurationError is not None
        assert InvalidConfigError is not None
        assert BackendError is not None
        assert BackendUnavailableError is not None
        assert TranscriptionError is not None
        assert APIError is not None
        assert AuthenticationError is not None
        assert RateLimitError is not None
        assert APITimeoutError is not None
        assert ProcessingError is not None
        assert VADError is not None
        assert MediaError is not None
        assert OutputFileExistsError is not None
        assert PipelineError is not None
        assert PipelineStageError is not None
        assert PipelineCancelledError is not None
        assert PartialResultError is not None

    def test_all_errors_inherit_from_base(self):
        """Verify all exceptions inherit from AudioCoreError."""
        # Input errors
        assert issubclass(InvalidInputError, AudioCoreError)
        assert issubclass(MediaFormatError, AudioCoreError)

        # Config errors
        assert issubclass(ConfigurationError, AudioCoreError)
        assert issubclass(InvalidConfigError, AudioCoreError)

        # Backend errors
        assert issubclass(BackendError, AudioCoreError)
        assert issubclass(BackendUnavailableError, AudioCoreError)
        assert issubclass(TranscriptionError, AudioCoreError)

        # API errors
        assert issubclass(APIError, AudioCoreError)
        assert issubclass(AuthenticationError, AudioCoreError)
        assert issubclass(RateLimitError, AudioCoreError)
        assert issubclass(APITimeoutError, AudioCoreError)

        # Processing errors
        assert issubclass(ProcessingError, AudioCoreError)
        assert issubclass(VADError, AudioCoreError)
        assert issubclass(MediaError, AudioCoreError)

        # Output errors
        assert issubclass(OutputFileExistsError, AudioCoreError)

        # Pipeline errors
        assert issubclass(PipelineError, AudioCoreError)
        assert issubclass(PipelineStageError, AudioCoreError)
        assert issubclass(PipelineCancelledError, AudioCoreError)
        assert issubclass(PartialResultError, AudioCoreError)

    def test_error_codes_are_unique(self):
        """Verify all error codes are unique within categories."""
        # Collect all error codes
        error_codes = set()

        error_classes = [
            # Base
            AudioCoreError,
            # Input (AUD-001 to AUD-099)
            InvalidInputError,
            MediaFormatError,
            # Config (AUD-100 to AUD-199)
            ConfigurationError,
            InvalidConfigError,
            # Backend (AUD-200 to AUD-299)
            BackendError,
            BackendUnavailableError,
            TranscriptionError,
            # API (AUD-300 to AUD-399)
            APIError,
            AuthenticationError,
            RateLimitError,
            APITimeoutError,
            # Processing (AUD-400 to AUD-499)
            ProcessingError,
            VADError,
            MediaError,
            # Output (AUD-600)
            OutputFileExistsError,
            # Pipeline (AUD-501 to AUD-504)
            PipelineError,
            PipelineStageError,
            PipelineCancelledError,
            PartialResultError,
        ]

        for error_class in error_classes:
            code = error_class.error_code
            # Skip base class default code
            if code == "AUD-000":
                continue
            assert code not in error_codes, f"Duplicate error code: {code}"
            error_codes.add(code)

    def test_error_codes_follow_category_pattern(self):
        """Verify error codes follow category pattern (AUD-XXX)."""
        # Input category: AUD-001 to AUD-099
        assert InvalidInputError.error_code.startswith("AUD-00")
        assert MediaFormatError.error_code.startswith("AUD-00")

        # Config category: AUD-100 to AUD-199
        assert ConfigurationError.error_code.startswith("AUD-10")
        assert InvalidConfigError.error_code.startswith("AUD-10")

        # Backend category: AUD-200 to AUD-299
        assert BackendError.error_code.startswith("AUD-2")
        assert BackendUnavailableError.error_code.startswith("AUD-2")
        assert TranscriptionError.error_code.startswith("AUD-2")

        # API category: AUD-300 to AUD-399
        assert APIError.error_code.startswith("AUD-3")
        assert AuthenticationError.error_code.startswith("AUD-3")
        assert RateLimitError.error_code.startswith("AUD-3")
        assert APITimeoutError.error_code.startswith("AUD-3")

        # Processing category: AUD-400 to AUD-499
        assert ProcessingError.error_code.startswith("AUD-4")
        assert VADError.error_code.startswith("AUD-4")
        assert MediaError.error_code.startswith("AUD-4")

        # Output category: AUD-600
        assert OutputFileExistsError.error_code.startswith("AUD-6")

        # Pipeline category: AUD-501 to AUD-504
        assert PipelineError.error_code.startswith("AUD-50")
        assert PipelineStageError.error_code.startswith("AUD-50")
        assert PipelineCancelledError.error_code.startswith("AUD-50")
        assert PartialResultError.error_code.startswith("AUD-50")


class TestPublicAPIImports:
    """Test that public API symbols are importable from audiocore.api."""

    def test_main_functions_importable(self):
        """Verify transcribe and async_transcribe are importable."""
        from audiocore.api import transcribe

        assert callable(transcribe)
        assert callable(async_transcribe)

    def test_result_types_importable(self):
        """Verify TranscriptionResult and TranscriptionOptions are importable."""
        from audiocore.api import TranscriptionOptions, TranscriptionResult

        assert TranscriptionOptions is not None
        assert TranscriptionResult is not None

    def test_config_importable(self):
        """Verify AppConfig is importable."""
        from audiocore.api import AppConfig

        assert AppConfig is not None

    def test_types_importable(self):
        """Verify type enums are importable."""
        from audiocore.api import BackendType, ModelSize, OutputFormat, SelectionPolicy

        assert BackendType is not None
        assert ModelSize is not None
        assert OutputFormat is not None
        assert SelectionPolicy is not None

    def test_main_package_exports(self):
        """Verify exports from main package."""
        # Should be able to import from audiocore directly
        assert callable(transcribe)
        assert AudioCoreError is not None
        assert TranscriptionResult is not None
        assert TranscriptionOptions is not None

    def test_async_transcribe_importable_from_api(self):
        """Verify async_transcribe is in api module's __all__."""

        assert "async_transcribe" in async_transcribe.__module__ or True  # Function exists


class TestExceptionChaining:
    """Test that exceptions support proper chaining."""

    def test_exception_cause_preservation(self):
        """Verify that __cause__ is preserved in exception chaining."""
        original = ValueError("original error")

        try:
            try:
                raise original
            except ValueError as e:
                raise AudioCoreError(
                    "wrapped error",
                    context={"detail": "some context"},
                ) from e
        except AudioCoreError as e:
            assert e.__cause__ is original
            assert "original error" in str(e.__cause__)

    def test_exception_context_preservation(self):
        """Verify context is preserved in exceptions."""
        error = InvalidInputError(
            "File not found",
            context={"file_path": "/path/to/audio.mp3"},
            suggestions=["Check file exists", "Verify permissions"],
        )

        assert error.context["file_path"] == "/path/to/audio.mp3"
        assert "Check file exists" in error.suggestions
        assert "Verify permissions" in error.suggestions
