"""OpenAI Whisper API backend implementation.

This module provides the OpenAI Whisper API integration for audio/video
transcription. It implements the TranscriptionBackend interface with
comprehensive error handling and API key protection.

Key Features:
- Lazy client initialization
- Automatic API key validation
- OpenAI exception mapping to AudioCore exceptions
- API key redaction in all error messages
- Support for multiple response formats (verbose_json)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from openai import OpenAI
from openai import (
    APIConnectionError,
    APIError as OpenAIAPIError,
    APITimeoutError,
    AuthenticationError as OpenAIAuthenticationError,
    RateLimitError as OpenAIRateLimitError,
)

from audiocore.errors import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    BackendUnavailableError,
    RateLimitError,
    TranscriptionError,
)
from audiocore.models import MediaInfo, Segment, TranscriptionOptions, TranscriptionResult
from audiocore.types import BackendType

from .base import TranscriptionBackend

logger = logging.getLogger(__name__)


class OpenAIBackend(TranscriptionBackend):
    """OpenAI Whisper API backend for transcription.

    Implements the TranscriptionBackend interface using OpenAI's Whisper API.
    Provides automatic error handling, API key validation, and lazy client
    initialization.

    Attributes:
        backend_type: Returns BackendType.OPENAI.
        _client: Lazily-initialized OpenAI client instance.
        _api_key: API key for OpenAI (optional, uses environment if not provided).

    Example:
        >>> backend = OpenAIBackend(api_key="sk-...")
        >>> if backend.is_available():
        ...     result = backend.transcribe("audio.mp3", TranscriptionOptions())
        ...     print(result.segments[0].text)

    Note:
        - API key can be set via OPENAI_API_KEY environment variable
        - All OpenAI exceptions are mapped to AudioCore exceptions
        - API keys are never logged or exposed in error messages

    Security:
        - API key is never logged
        - API key is redacted from all error messages
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize OpenAI backend.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY
                environment variable.

        Note:
            Client is lazily initialized on first transcribe() call.
        """
        self._client: OpenAI | None = None
        self._api_key: str | None = api_key

    @property
    def backend_type(self) -> BackendType:
        """Return the backend type identifier.

        Returns:
            BackendType.OPENAI enum value.
        """
        return BackendType.OPENAI

    def get_name(self) -> str:
        """Return human-readable backend name.

        Returns:
            "OpenAI Whisper API" display name.
        """
        return "OpenAI Whisper API"

    def is_available(self) -> bool:
        """Check if OpenAI backend is available.

        Checks that an API key is configured (either via constructor or
        environment variable) and validates that it has the correct format.

        Returns:
            True if API key is configured and has correct format, False otherwise.
        """
        # Check if API key is provided in constructor
        if self._api_key is not None:
            return self._api_key.startswith("sk-")

        # Check environment variable
        import os

        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key is not None:
            return env_key.startswith("sk-")

        return False

    def get_model_options(self) -> list[str]:
        """Return valid model options for OpenAI Whisper API.

        Returns:
            List containing "whisper-1" (the only supported model).
        """
        return ["whisper-1"]

    def _get_client(self) -> OpenAI:
        """Get or create OpenAI client.

        Lazy initialization - creates client on first call.

        Returns:
            OpenAI client instance.

        Raises:
            BackendUnavailableError: If API key is not configured.
        """
        if self._client is None:
            # Determine API key source
            api_key = self._api_key
            if api_key is None:
                import os

                api_key = os.environ.get("OPENAI_API_KEY")

            if not api_key:
                raise BackendUnavailableError(
                    "OpenAI API key not configured",
                    context={"backend": "openai"},
                    suggestions=[
                        "Set OPENAI_API_KEY environment variable",
                        "Pass api_key parameter to OpenAIBackend constructor",
                    ],
                )

            self._client = OpenAI(api_key=api_key)

        return self._client

    def _redact_api_key(self, message: str) -> str:
        """Redact API key from error messages.

        Args:
            message: Error message potentially containing API key.

        Returns:
            Message with API key replaced with "[REDACTED]".
        """
        # Redact constructor-provided key
        if self._api_key and self._api_key in message:
            message = message.replace(self._api_key, "[REDACTED]")

        # Redact environment key if available
        import os

        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key and env_key in message:
            message = message.replace(env_key, "[REDACTED]")

        return message

    def transcribe(
        self, audio_path: Path | str, options: TranscriptionOptions
    ) -> TranscriptionResult:
        """Transcribe an audio/video file using OpenAI Whisper API.

        Makes a request to OpenAI's Whisper API, handles all error types,
        and returns structured transcription results.

        Args:
            audio_path: Path to the audio/video file to transcribe.
            options: Transcription configuration options.

        Returns:
            TranscriptionResult with segments, media_info, and metadata.

        Raises:
            BackendUnavailableError: If API key is not configured.
            AuthenticationError: If API key is invalid.
            RateLimitError: If rate limit is exceeded.
            APITimeoutError: If request times out.
            APIError: For other API-related errors.
            TranscriptionError: For transcription failures.

        Security:
            - API key is never logged or included in error messages
            - All error messages are redacted before being raised
        """
        audio_path = Path(audio_path)

        # Validate file exists
        if not audio_path.exists():
            raise TranscriptionError(
                f"Audio file not found: {audio_path}",
                context={"file_path": str(audio_path), "backend": "openai"},
                suggestions=[
                    "Verify the file path is correct",
                    "Check the file exists",
                ],
            )

        # Log transcription start (without API key)
        logger.debug(
            "Starting OpenAI transcription for %s",
            audio_path,
        )

        start_time = time.time()
        # Initialize api_params for error handling (file opened in try block)
        api_params: dict[str, object] = {}

        try:
            client = self._get_client()

            # Build API call parameters
            api_params = {
                "model": "whisper-1",
                "file": open(audio_path, "rb"),  # Open file in binary mode
                "response_format": "verbose_json",  # Get segments with timestamps
            }

            # Add optional parameters
            if options.language:
                api_params["language"] = options.language

            # Map model_size to temperature (affects output variability)
            # smaller models = lower temperature (more deterministic)
            temperature_map: dict[str, float] = {
                "tiny": 0.0,
                "base": 0.0,
                "small": 0.2,
                "medium": 0.4,
                "large": 0.6,
            }
            api_params["temperature"] = temperature_map.get(options.model_size.value, 0.0)

            # Make the API call
            response = client.audio.transcriptions.create(**api_params)  # type: ignore[arg-type]

            # Close file handle
            api_params["file"].close()  # type: ignore[union-attr]

        except BackendUnavailableError:
            # Re-raise BackendUnavailableError without wrapping
            raise

        except OpenAIAuthenticationError as e:
            self._safe_close_file(api_params)
            message = self._redact_api_key(str(e))
            raise AuthenticationError(
                f"OpenAI authentication failed: {message}",
                context={"backend": "openai"},
                suggestions=[
                    "Verify API key at https://platform.openai.com/api-keys",
                    "Check API key is not expired or revoked",
                    "Ensure API key has Whisper permissions",
                ],
                cause=e,
            ) from e

        except OpenAIRateLimitError as e:
            self._safe_close_file(api_params)
            # Extract retry_after from response if available
            retry_after = None
            if hasattr(e, "response") and e.response is not None:
                retry_after_header = e.response.headers.get("retry-after")
                if retry_after_header:
                    try:
                        retry_after = int(retry_after_header)
                    except ValueError:
                        pass

            context: dict[str, object] = {"backend": "openai"}
            if retry_after:
                context["retry_after"] = retry_after

            raise RateLimitError(
                "OpenAI rate limit exceeded",
                context=context,
                suggestions=[
                    f"Wait {retry_after} seconds before retrying"
                    if retry_after
                    else "Wait before retrying",
                    "Consider upgrading API tier",
                    "Implement request throttling",
                ],
            ) from e

        except APITimeoutError as e:
            self._safe_close_file(api_params)
            raise APITimeoutError(
                "OpenAI API request timed out",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Retry with shorter audio file",
                    "Check network connection",
                    "Increase timeout configuration",
                ],
                cause=e,
            ) from e

        except APIConnectionError as e:
            self._safe_close_file(api_params)
            message = self._redact_api_key(str(e))
            raise APIError(
                f"OpenAI connection error: {message}",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Check network connectivity",
                    "Verify firewall settings",
                    "Try again later",
                ],
                cause=e,
            ) from e

        except OpenAIAPIError as e:
            self._safe_close_file(api_params)
            message = self._redact_api_key(str(e))
            raise APIError(
                f"OpenAI API error: {message}",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Check API service status",
                    "Verify request parameters",
                    "Try again later",
                ],
                cause=e,
            ) from e

        except Exception as e:
            self._safe_close_file(api_params)
            message = self._redact_api_key(str(e))
            raise TranscriptionError(
                f"OpenAI transcription failed: {message}",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Check audio file format",
                    "Verify audio file is valid",
                    "Try with different file",
                ],
                cause=e,
            ) from e

        # Process successful response
        end_time = time.time()
        duration_seconds = end_time - start_time

        try:
            # Extract segments from verbose_json response
            segments: list[Segment] = []
            if hasattr(response, "segments") and response.segments:
                for seg in response.segments:
                    segments.append(
                        Segment(
                            start_time=seg.start,  # type: ignore[arg-type]
                            end_time=seg.end,  # type: ignore[arg-type]
                            text=seg.text,  # type: ignore[arg-type]
                        )
                    )

            # Get duration from response or calculate from last segment
            media_duration: float
            if hasattr(response, "duration") and response.duration:
                media_duration = response.duration
            elif segments:
                media_duration = segments[-1].end_time
            else:
                # Use a small minimum duration since MediaInfo requires duration > 0
                media_duration = 0.01

            # Build media info
            media_info = MediaInfo(
                duration=media_duration,
                format=audio_path.suffix.lstrip("."),
            )

            # Build transcription result
            result = TranscriptionResult(
                segments=segments,
                media_info=media_info,
                config_used=options,
                duration_seconds=duration_seconds,
                backend_used=BackendType.OPENAI,
            )

            logger.debug(
                "OpenAI transcription complete for %s: %d segments, %.2fs processing",
                audio_path,
                len(segments),
                duration_seconds,
            )

            return result

        except Exception as e:
            raise TranscriptionError(
                f"Failed to parse OpenAI response: {self._redact_api_key(str(e))}",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Check API response format",
                    "Try with different audio file",
                ],
                cause=e,
            ) from e

    def _safe_close_file(self, api_params: dict[str, object]) -> None:
        """Safely close file handle in error cases.

        Args:
            api_params: API parameters dict that may contain an open file.
        """
        if "file" in api_params:
            try:
                api_params["file"].close()  # type: ignore[union-attr]
            except Exception:
                pass  # Ignore close errors in error handling
