"""Backend availability checking without network calls."""

from dataclasses import dataclass

from audiocore.backends.registry import BackendRegistry
from audiocore.config import AppConfig
from audiocore.types import BackendType


@dataclass
class BackendStatus:
    """Status information for a backend."""

    backend_type: BackendType
    available: bool
    reason: str | None = None
    suggestion: str | None = None


class BackendAvailabilityChecker:
    """Check backend availability without network calls."""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()
        self._registry = BackendRegistry()

    def check_backend(self, backend_type: BackendType) -> BackendStatus:
        """Check if a backend is available and ready to use."""
        if backend_type == BackendType.OPENAI:
            return self._check_openai()
        elif backend_type == BackendType.FASTER_WHISPER:
            return self._check_faster_whisper()
        elif backend_type == BackendType.AUTO:
            return BackendStatus(
                backend_type=backend_type,
                available=False,
                reason="AUTO is not a concrete backend type",
                suggestion="Use BackendType.OPENAI or BackendType.FASTER_WHISPER",
            )
        else:
            return BackendStatus(
                backend_type=backend_type,
                available=False,
                reason=f"Unknown backend type: {backend_type}",
                suggestion=f"Use one of: {list(BackendType)}",
            )

    def check_all(self) -> list[BackendStatus]:
        """Check availability of all registered backends."""
        statuses = []
        for backend_type in [BackendType.OPENAI, BackendType.FASTER_WHISPER]:
            statuses.append(self.check_backend(backend_type))
        return statuses

    def get_available_backends(self) -> list[BackendType]:
        """Get list of available backend types."""
        return [status.backend_type for status in self.check_all() if status.available]

    def _check_openai(self) -> BackendStatus:
        """Check OpenAI backend availability."""
        api_key = self._get_openai_api_key()

        if not api_key:
            return BackendStatus(
                backend_type=BackendType.OPENAI,
                available=False,
                reason="OpenAI API key not configured",
                suggestion="Set OPENAI_API_KEY environment variable or configure in audiocore.toml",
            )

        return BackendStatus(
            backend_type=BackendType.OPENAI,
            available=True,
            reason="API key configured",
            suggestion=None,
        )

    def _check_faster_whisper(self) -> BackendStatus:
        """Check faster-whisper backend availability.

        Performs both import check and basic runtime verification
        to ensure faster-whisper and its dependencies are working.

        Returns:
            BackendStatus with availability info.
        """
        try:
            import faster_whisper  # noqa: F401 - Import used for availability check
            from faster_whisper import (
                WhisperModel,  # noqa: F401 - Import used for availability check
            )

            # Verify CTranslate2 is functional by checking the backend attribute
            try:
                from ctranslate2 import get_supported_compute_types  # noqa: F401

                return BackendStatus(
                    backend_type=BackendType.FASTER_WHISPER,
                    available=True,
                    reason="faster-whisper module installed and dependencies verified",
                    suggestion=None,
                )
            except (ImportError, RuntimeError) as dep_error:
                return BackendStatus(
                    backend_type=BackendType.FASTER_WHISPER,
                    available=False,
                    reason=f"faster-whisper dependencies not working: {dep_error}",
                    suggestion="Reinstall faster-whisper: pip install --force-reinstall faster-whisper",
                )
        except ImportError:
            return BackendStatus(
                backend_type=BackendType.FASTER_WHISPER,
                available=False,
                reason="faster-whisper not installed",
                suggestion="Install with: pip install faster-whisper",
            )

    def _get_openai_api_key(self) -> str | None:
        """Get OpenAI API key from config or environment."""
        if self.config.openai and self.config.openai.api_key:
            key = self.config.openai.api_key.get_secret_value()
            return key if key else None

        import os

        return os.environ.get("OPENAI_API_KEY")
