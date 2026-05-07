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
- Configuration via OpenAIConfig
"""

from __future__ import annotations

import contextlib
import logging
import math
import subprocess
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from openai import (
    APIConnectionError,
    OpenAI,
)
from openai import (
    APIError as OpenAIAPIError,
)
from openai import (
    APITimeoutError as OpenAITimeoutError,
)
from openai import (
    AuthenticationError as OpenAIAuthenticationError,
)
from openai import (
    RateLimitError as OpenAIRateLimitError,
)

from audiocore.errors import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    BackendUnavailableError,
    InvalidInputError,
    RateLimitError,
    TranscriptionError,
)
from audiocore.models import (
    MediaInfo,
    Segment,
    TranscriptionOptions,
    TranscriptionResult,
)
from audiocore.types import BackendType

from .base import TranscriptionBackend

if TYPE_CHECKING:
    from audiocore.config import AppConfig
    from audiocore.config.openai_config import OpenAIConfig

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MAX_UPLOAD_SIZE_MB = 25.0
DEFAULT_OPENAI_CHUNK_TARGET_SIZE_MB = 24.0
DEFAULT_OPENAI_CHUNK_MIN_DURATION_SECONDS = 30.0
DEFAULT_OPENAI_CHUNK_PROMPT_CHARS = 1000
CHUNK_SIZE_RETRY_MARGIN = 0.9
MAX_CHUNK_SIZE_ATTEMPTS = 5


def _get_response_value(obj: object, key: str) -> object | None:
    """Read an OpenAI response field from SDK objects or dict-compatible data."""
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _parse_positive_duration(value: object) -> float | None:
    """Parse positive finite durations from provider responses."""
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(duration) or duration <= 0:
        return None
    return duration


class OpenAIBackend(TranscriptionBackend):
    """OpenAI Whisper API backend for transcription.

    Implements the TranscriptionBackend interface using OpenAI's Whisper API.
    Provides automatic error handling, API key validation, and lazy client
    initialization.

    Attributes:
        backend_type: Returns BackendType.OPENAI.
        _client: Lazily-initialized OpenAI client instance.
        _api_key: API key for OpenAI (optional, uses environment if not provided).
        _config: OpenAIConfig instance (optional, provides configuration).

    Example:
        >>> from audiocore.config.openai_config import OpenAIConfig
        >>> config = OpenAIConfig(api_key="sk-...")
        >>> backend = OpenAIBackend(config=config)
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

    def __init__(
        self,
        api_key: str | None = None,
        config: OpenAIConfig | AppConfig | None = None,
    ) -> None:
        """Initialize OpenAI backend.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY
                environment variable. (deprecated: use config instead)
            config: OpenAIConfig or AppConfig instance. If AppConfig is provided,
                the openai sub-config is extracted. If OpenAIConfig is provided
                directly, it is used as-is.

        Note:
            Client is lazily initialized on first transcribe() call.
            Priority: config.api_key > api_key > OPENAI_API_KEY env var
        """
        self._client: OpenAI | None = None
        self._api_key: str | None = None
        self._ffmpeg_path = "ffmpeg"
        self._ffprobe_path = "ffprobe"

        # Handle AppConfig passed from BackendRegistry
        from audiocore.config import AppConfig

        if isinstance(config, AppConfig):
            self._ffmpeg_path = config.ffmpeg_path
            self._ffprobe_path = config.ffprobe_path
            config = config.openai
        self._config: OpenAIConfig | None = config

        # Extract API key from config if provided
        if config is not None and config.api_key is not None:
            self._api_key = config.api_key.get_secret_value()
        elif api_key is not None:
            self._api_key = api_key

        # Log initialization status
        init_source = (
            "config"
            if config is not None
            else ("api_key" if api_key is not None else "environment")
        )
        logger.debug("OpenAIBackend initialized with %s", init_source)

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

        Checks that the openai package is installed and an API key is
        configured (either via constructor or environment variable).

        Returns:
            True if openai package is installed and API key is configured, False otherwise.
        """
        try:
            import openai  # noqa: F401
        except ImportError:
            return False

        return self._resolve_api_key() is not None

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
            api_key = self._resolve_api_key()

            if api_key is None:
                raise BackendUnavailableError(
                    "OpenAI API key not configured",
                    context={"backend": "openai"},
                    suggestions=[
                        "Set OPENAI_API_KEY environment variable",
                        "Pass config parameter to OpenAIBackend constructor",
                        "Pass api_key parameter to OpenAIBackend constructor",
                    ],
                )

            # Build client kwargs from config if available
            client_kwargs: dict[str, object] = {"api_key": api_key}
            if self._config is not None:
                if self._config.organization is not None:
                    client_kwargs["organization"] = self._config.organization
                if self._config.base_url is not None:
                    client_kwargs["base_url"] = self._config.base_url
                if self._config.timeout:
                    client_kwargs["timeout"] = self._config.timeout
                if self._config.max_retries is not None:
                    client_kwargs["max_retries"] = self._config.max_retries

            self._client = OpenAI(**client_kwargs)  # type: ignore[arg-type]

        return self._client

    def _resolve_api_key(self) -> str | None:
        """Resolve the first non-blank API key by priority."""
        if self._api_key and self._api_key.strip():
            return self._api_key.strip()

        import os

        for key in (os.environ.get("OPENAI_API_KEY"), os.environ.get("AUDIOCORE_OPENAI_API_KEY")):
            if key and key.strip():
                return key.strip()
        return None

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
        if self._api_key:
            stripped_api_key = self._api_key.strip()
            if stripped_api_key and stripped_api_key in message:
                message = message.replace(stripped_api_key, "[REDACTED]")

        # Redact environment keys
        import os

        for env_var in ("OPENAI_API_KEY", "AUDIOCORE_OPENAI_API_KEY"):
            env_key = os.environ.get(env_var)
            if env_key and env_key in message:
                message = message.replace(env_key, "[REDACTED]")
            if env_key:
                stripped_env_key = env_key.strip()
                if stripped_env_key and stripped_env_key in message:
                    message = message.replace(stripped_env_key, "[REDACTED]")

        return message

    def close(self) -> None:
        """Close the OpenAI client and release connection pool resources."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __del__(self) -> None:
        """Ensure client connection pool is released on garbage collection."""
        with contextlib.suppress(Exception):
            self.close()

    @property
    def _max_upload_bytes(self) -> int:
        size_mb = (
            self._config.max_upload_size_mb
            if self._config is not None
            else DEFAULT_OPENAI_MAX_UPLOAD_SIZE_MB
        )
        return int(size_mb * 1_000_000)

    @property
    def _chunk_target_bytes(self) -> int:
        size_mb = (
            self._config.chunk_target_size_mb
            if self._config is not None
            else DEFAULT_OPENAI_CHUNK_TARGET_SIZE_MB
        )
        return int(size_mb * 1_000_000)

    @property
    def _chunk_min_duration_seconds(self) -> float:
        if self._config is not None:
            return self._config.chunk_min_duration_seconds
        return DEFAULT_OPENAI_CHUNK_MIN_DURATION_SECONDS

    @property
    def _chunk_prompt_chars(self) -> int:
        if self._config is not None:
            return self._config.chunk_prompt_chars
        return DEFAULT_OPENAI_CHUNK_PROMPT_CHARS

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
            raise InvalidInputError(
                f"Audio file not found: {audio_path}",
                context={"file_path": str(audio_path), "backend": "openai"},
                suggestions=[
                    "Verify the file path is correct",
                    "Check the file exists",
                ],
            )
        if not audio_path.is_file():
            raise InvalidInputError(
                f"Audio path is not a file: {audio_path}",
                context={"file_path": str(audio_path), "backend": "openai"},
                suggestions=[
                    "Provide an audio file path, not a directory",
                    "Verify the file path is correct",
                ],
            )

        # Log transcription start (without API key)
        logger.debug(
            "Starting OpenAI transcription for %s",
            audio_path,
        )

        if audio_path.stat().st_size > self._max_upload_bytes:
            return self._transcribe_large_file(audio_path, options)
        return self._transcribe_single_file(audio_path, options)

    def _transcribe_single_file(
        self,
        audio_path: Path,
        options: TranscriptionOptions,
        *,
        prompt: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe one file that fits within the OpenAI upload limit."""
        start_time = time.time()
        response = self._request_transcription(audio_path, options, prompt=prompt)
        processing_time_seconds = time.time() - start_time
        return self._parse_transcription_response(
            response=response,
            audio_path=audio_path,
            options=options,
            processing_time_seconds=processing_time_seconds,
        )

    def _request_transcription(
        self,
        audio_path: Path,
        options: TranscriptionOptions,
        *,
        prompt: str | None = None,
    ) -> object:
        """Call OpenAI's transcription API and map provider errors."""
        audio_file = None
        try:
            client = self._get_client()

            # Build API call parameters
            # SIM115: File handle closed in finally block and error handlers
            audio_file = open(audio_path, "rb")  # noqa: SIM115
            api_params = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json",  # Get segments with timestamps
            }

            # Add optional parameters
            if options.language:
                api_params["language"] = options.language
            if prompt:
                api_params["prompt"] = prompt

            # Make the API call
            return client.audio.transcriptions.create(**api_params)  # type: ignore[arg-type]

        except BackendUnavailableError:
            # Re-raise BackendUnavailableError without wrapping
            raise

        except OpenAIAuthenticationError as e:
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
            # Extract retry_after from response if available
            retry_after = None
            if hasattr(e, "response") and e.response is not None:
                retry_after_header = e.response.headers.get("retry-after")
                if retry_after_header:
                    with contextlib.suppress(ValueError):
                        retry_after = int(retry_after_header)

            context: dict[str, object] = {"backend": "openai"}
            if retry_after:
                context["retry_after"] = retry_after

            raise RateLimitError(
                "OpenAI rate limit exceeded",
                context=context,
                suggestions=[
                    (
                        f"Wait {retry_after} seconds before retrying"
                        if retry_after
                        else "Wait before retrying"
                    ),
                    "Consider upgrading API tier",
                    "Implement request throttling",
                ],
            ) from e

        except OpenAITimeoutError as e:
            raise APITimeoutError(
                "OpenAI API request timed out",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Retry with shorter audio file",
                    "Check network connection",
                    "Increase timeout configuration",
                ],
            ) from e

        except APIConnectionError as e:
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

        finally:
            # Always close the file handle, whether the API call succeeded or failed
            if audio_file is not None:
                with contextlib.suppress(Exception):
                    audio_file.close()

    def _parse_transcription_response(
        self,
        response: object,
        audio_path: Path,
        options: TranscriptionOptions,
        processing_time_seconds: float,
    ) -> TranscriptionResult:
        """Parse an OpenAI response into AudioCore's result model."""
        try:
            # Extract segments from verbose_json response
            segments: list[Segment] = []
            response_segments = _get_response_value(response, "segments")
            if response_segments:
                for seg in cast("list[object]", response_segments):
                    start = _get_response_value(seg, "start")
                    end = _get_response_value(seg, "end")
                    text = _get_response_value(seg, "text")
                    segments.append(
                        Segment(
                            start_time=float(start),  # type: ignore[arg-type]
                            end_time=float(end),  # type: ignore[arg-type]
                            text=text if isinstance(text, str) else str(text or ""),
                        )
                    )

            # Get duration from response or calculate from last segment
            media_duration: float
            response_duration = _parse_positive_duration(_get_response_value(response, "duration"))
            if response_duration is not None:
                media_duration = response_duration
            elif segments:
                media_duration = max(segment.end_time for segment in segments)
            else:
                # Use a small minimum duration since MediaInfo requires duration > 0
                media_duration = 0.01

            # Some compatible providers may return top-level text without segment
            # details even when verbose_json was requested. Preserve that text
            # instead of returning an empty transcription.
            response_text = _get_response_value(response, "text")
            if not segments and isinstance(response_text, str) and response_text.strip():
                segments.append(
                    Segment(
                        start_time=0.0,
                        end_time=media_duration,
                        text=response_text.strip(),
                    )
                )

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
                processing_time_seconds=processing_time_seconds,
                backend_used=BackendType.OPENAI,
            )

            logger.debug(
                "OpenAI transcription complete for %s: %d segments, %.2fs processing",
                audio_path,
                len(segments),
                processing_time_seconds,
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

    def _transcribe_large_file(
        self, audio_path: Path, options: TranscriptionOptions
    ) -> TranscriptionResult:
        """Split oversized audio and combine per-chunk OpenAI transcriptions."""
        start_time = time.time()
        chunks = self._split_audio_for_upload(audio_path)
        logger.debug(
            "OpenAI transcription split %s into %d chunks",
            audio_path,
            len(chunks),
        )

        combined_segments: list[Segment] = []
        transcript_tail = ""
        duration_offset = 0.0
        total_duration = 0.0

        try:
            for index, chunk_path in enumerate(chunks, start=1):
                prompt = self._build_chunk_prompt(transcript_tail)
                chunk_result = self._transcribe_single_file(chunk_path, options, prompt=prompt)
                chunk_duration = self._get_audio_duration(chunk_path)
                total_duration += chunk_duration

                for segment in chunk_result.segments:
                    combined_segments.append(
                        Segment(
                            start_time=segment.start_time + duration_offset,
                            end_time=segment.end_time + duration_offset,
                            text=segment.text,
                            confidence=segment.confidence,
                        )
                    )

                chunk_text = " ".join(
                    segment.text.strip()
                    for segment in chunk_result.segments
                    if segment.text.strip()
                )
                if chunk_text and self._chunk_prompt_chars > 0:
                    next_tail = (
                        f"{transcript_tail}\n{chunk_text}" if transcript_tail else chunk_text
                    )
                    transcript_tail = next_tail[-self._chunk_prompt_chars :]

                logger.debug(
                    "OpenAI transcription chunk %d/%d complete for %s",
                    index,
                    len(chunks),
                    audio_path,
                )
                duration_offset += chunk_duration
        finally:
            if chunks:
                self._cleanup_chunk_dir(chunks[0].parent)

        return TranscriptionResult(
            segments=combined_segments,
            media_info=MediaInfo(
                duration=total_duration if total_duration > 0 else 0.01,
                format=audio_path.suffix.lstrip("."),
            ),
            config_used=options,
            processing_time_seconds=time.time() - start_time,
            backend_used=BackendType.OPENAI,
        )

    def _build_chunk_prompt(self, transcript_tail: str) -> str | None:
        """Build continuity prompt text for the next OpenAI chunk."""
        if self._chunk_prompt_chars <= 0 or not transcript_tail:
            return None
        return transcript_tail[-self._chunk_prompt_chars :]

    def _split_audio_for_upload(self, audio_path: Path) -> list[Path]:
        """Create temporary chunks that fit below the configured upload limit."""
        duration = self._get_audio_duration(audio_path)
        if duration <= 0:
            raise TranscriptionError(
                "Cannot split audio with unknown duration",
                context={"backend": "openai", "file_path": str(audio_path)},
                suggestions=[
                    "Verify ffprobe can read the audio file",
                    "Try a different audio format",
                ],
            )

        chunk_duration = self._estimate_chunk_duration(audio_path, duration)
        temp_dir = Path(tempfile.mkdtemp(prefix="audiocore_openai_chunks_"))

        for _attempt in range(MAX_CHUNK_SIZE_ATTEMPTS):
            self._run_ffmpeg_segment(audio_path, temp_dir, chunk_duration)
            chunks = sorted(temp_dir.glob("chunk_*.*"))
            if not chunks:
                self._cleanup_chunk_dir(temp_dir)
                raise TranscriptionError(
                    "ffmpeg did not create any audio chunks",
                    context={"backend": "openai", "file_path": str(audio_path)},
                    suggestions=[
                        "Verify ffmpeg can read the audio file",
                        "Try a different audio format",
                    ],
                )

            largest_chunk_size = max(chunk.stat().st_size for chunk in chunks)
            if largest_chunk_size <= self._max_upload_bytes:
                return chunks

            self._cleanup_chunk_files(temp_dir)
            reduction_ratio = self._chunk_target_bytes / largest_chunk_size
            next_duration = chunk_duration * reduction_ratio * CHUNK_SIZE_RETRY_MARGIN
            if next_duration < self._chunk_min_duration_seconds:
                self._cleanup_chunk_dir(temp_dir)
                raise TranscriptionError(
                    "Unable to split audio into chunks below OpenAI upload limit",
                    context={
                        "backend": "openai",
                        "file_path": str(audio_path),
                        "largest_chunk_size": largest_chunk_size,
                        "max_upload_size": self._max_upload_bytes,
                    },
                    suggestions=[
                        "Use a more compressed audio format",
                        "Increase openai.max_upload_size_mb if your provider supports it",
                    ],
                )
            chunk_duration = next_duration

        self._cleanup_chunk_dir(temp_dir)
        raise TranscriptionError(
            "Unable to produce OpenAI-sized chunks after retries",
            context={"backend": "openai", "file_path": str(audio_path)},
            suggestions=[
                "Use a more compressed audio format",
                "Try reducing openai.chunk_target_size_mb",
            ],
        )

    def _estimate_chunk_duration(self, audio_path: Path, duration: float) -> float:
        """Estimate chunk duration from observed file bitrate and target size."""
        file_size = audio_path.stat().st_size
        seconds_for_target_size = duration * (self._chunk_target_bytes / file_size)
        return max(self._chunk_min_duration_seconds, seconds_for_target_size)

    def _run_ffmpeg_segment(
        self,
        audio_path: Path,
        output_dir: Path,
        chunk_duration: float,
    ) -> None:
        """Split audio with ffmpeg into same-container chunks."""
        self._cleanup_chunk_files(output_dir)
        suffix = audio_path.suffix or ".wav"
        output_pattern = output_dir / f"chunk_%04d{suffix}"
        command = [
            self._ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(audio_path),
            "-f",
            "segment",
            "-segment_time",
            f"{chunk_duration:.6f}",
            "-reset_timestamps",
            "1",
            "-c",
            "copy",
            str(output_pattern),
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
            )
        except FileNotFoundError as e:
            self._cleanup_chunk_dir(output_dir)
            raise TranscriptionError(
                f"ffmpeg executable not found: {self._ffmpeg_path}",
                context={"backend": "openai", "ffmpeg_path": self._ffmpeg_path},
                suggestions=[
                    "Install ffmpeg",
                    "Set AppConfig.ffmpeg_path to the ffmpeg executable",
                ],
                cause=e,
            ) from e
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            self._cleanup_chunk_dir(output_dir)
            stderr = getattr(e, "stderr", None)
            raise TranscriptionError(
                "Failed to split oversized audio for OpenAI transcription",
                context={
                    "backend": "openai",
                    "file_path": str(audio_path),
                    "stderr": str(stderr)[:1000] if stderr else None,
                },
                suggestions=[
                    "Verify the audio file is valid",
                    "Verify ffmpeg supports this format",
                ],
                cause=e,
            ) from e

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Read audio duration in seconds with ffprobe."""
        command = [
            self._ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            duration = _parse_positive_duration(result.stdout.strip())
            if duration is None:
                raise ValueError("ffprobe returned a non-positive or non-finite duration")
            return duration
        except (
            FileNotFoundError,
            ValueError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as e:
            raise TranscriptionError(
                "Failed to read audio duration before OpenAI chunking",
                context={
                    "backend": "openai",
                    "file_path": str(audio_path),
                    "ffprobe_path": self._ffprobe_path,
                },
                suggestions=[
                    "Verify ffprobe is installed",
                    "Set AppConfig.ffprobe_path to the ffprobe executable",
                    "Verify the audio file is valid",
                ],
                cause=e,
            ) from e

    def _cleanup_chunk_files(self, output_dir: Path) -> None:
        for chunk_path in output_dir.glob("chunk_*.*"):
            chunk_path.unlink(missing_ok=True)

    def _cleanup_chunk_dir(self, output_dir: Path) -> None:
        self._cleanup_chunk_files(output_dir)
        with contextlib.suppress(OSError):
            output_dir.rmdir()
