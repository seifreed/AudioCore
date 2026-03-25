"""Policy-based backend selection with fallback logic."""

import logging

from audiocore.backends.availability import BackendAvailabilityChecker
from audiocore.backends.registry import BackendRegistry
from audiocore.config import AppConfig
from audiocore.errors import BackendUnavailableError
from audiocore.types import BackendType, SelectionPolicy

logger = logging.getLogger(__name__)


class BackendSelector:
    """Select backend based on policy and availability."""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig()
        self._checker = BackendAvailabilityChecker(config=self.config)
        self._registry = BackendRegistry()

    def select(
        self,
        backend: BackendType = BackendType.AUTO,
        policy: SelectionPolicy = SelectionPolicy.AUTO,
    ) -> BackendType:
        """Select a backend based on policy and availability.

        Args:
            backend: Explicit backend selection (AUTO for policy-based selection)
            policy: Selection policy (AUTO, PREFER_LOCAL, PREFER_CLOUD)

        Returns:
            Selected BackendType (OPENAI or FASTER_WHISPER)

        Raises:
            ValueError: If AUTO is passed as explicit backend
            BackendUnavailableError: If no backend is available
        """
        if backend == BackendType.AUTO:
            if policy == SelectionPolicy.AUTO:
                return self._select_auto()
            return self._select_by_policy(policy)

        return self._validate_backend(backend)

    def _validate_backend(self, backend: BackendType) -> BackendType:
        """Validate that the explicitly selected backend is available."""
        if backend == BackendType.AUTO:
            raise ValueError(
                "AUTO is not a valid explicit backend selection. Use OPENAI or FASTER_WHISPER."
            )

        status = self._checker.check_backend(backend)

        if not status.available:
            raise BackendUnavailableError(
                message=f"Backend {backend.value} is not available: {status.reason}",
                context={
                    "backend": backend.value,
                    "reason": status.reason,
                },
                suggestions=[status.suggestion] if status.suggestion else [],
            )

        return backend

    def _select_by_policy(self, policy: SelectionPolicy) -> BackendType:
        """Select backend based on policy."""
        if policy == SelectionPolicy.PREFER_LOCAL:
            return self._select_prefer_local()
        elif policy == SelectionPolicy.PREFER_CLOUD:
            return self._select_prefer_cloud()
        else:
            return self._select_auto()

    def _select_prefer_local(self) -> BackendType:
        """Select backend with preference for local (faster-whisper)."""
        fw_status = self._checker.check_backend(BackendType.FASTER_WHISPER)

        if fw_status.available:
            logger.debug("Selected faster-whisper (local preference)")
            return BackendType.FASTER_WHISPER

        openai_status = self._checker.check_backend(BackendType.OPENAI)

        if openai_status.available:
            logger.debug("Selected OpenAI (fallback for local preference)")
            return BackendType.OPENAI

        raise BackendUnavailableError(
            message="No backends available",
            context={"policy": "prefer_local"},
            suggestions=[
                "Install faster-whisper: pip install faster-whisper",
                "Or configure OpenAI API key: export OPENAI_API_KEY=<key>",
            ],
        )

    def _select_prefer_cloud(self) -> BackendType:
        """Select backend with preference for cloud (OpenAI)."""
        openai_status = self._checker.check_backend(BackendType.OPENAI)

        if openai_status.available:
            logger.debug("Selected OpenAI (cloud preference)")
            return BackendType.OPENAI

        fw_status = self._checker.check_backend(BackendType.FASTER_WHISPER)

        if fw_status.available:
            logger.debug("Selected faster-whisper (fallback for cloud preference)")
            return BackendType.FASTER_WHISPER

        raise BackendUnavailableError(
            message="No backends available",
            context={"policy": "prefer_cloud"},
            suggestions=[
                "Configure OpenAI API key: export OPENAI_API_KEY=<key>",
                "Or install faster-whisper: pip install faster-whisper",
            ],
        )

    def _select_auto(self) -> BackendType:
        """Select fastest available backend automatically.

        Priority order:
        1. CUDA/MPS faster-whisper (GPU accelerated)
        2. OpenAI (if API key configured)
        3. CPU faster-whisper
        """
        fw_status = self._checker.check_backend(BackendType.FASTER_WHISPER)
        openai_status = self._checker.check_backend(BackendType.OPENAI)

        if fw_status.available:
            logger.debug("Selected faster-whisper (auto selection)")
            return BackendType.FASTER_WHISPER

        if openai_status.available:
            logger.debug("Selected OpenAI (auto selection)")
            return BackendType.OPENAI

        raise BackendUnavailableError(
            message="No backends available",
            context={"policy": "auto"},
            suggestions=[
                "Install faster-whisper: pip install faster-whisper",
                "Or configure OpenAI API key: export OPENAI_API_KEY=<key>",
            ],
        )

    def get_backend(self, backend: BackendType):
        """Get backend instance for the selected backend type.

        Args:
            backend: Backend type to retrieve

        Returns:
            TranscriptionBackend instance
        """
        return self._registry.get_backend(backend)

    def get_available_backends(self) -> list[BackendType]:
        """Get list of all available backend types."""
        return self._checker.get_available_backends()


def select_backend(
    backend: BackendType = BackendType.AUTO,
    policy: SelectionPolicy = SelectionPolicy.AUTO,
    config: AppConfig | None = None,
) -> BackendType:
    """Convenience function for backend selection.

    Args:
        backend: Explicit backend selection (AUTO for policy-based selection)
        policy: Selection policy (AUTO, PREFER_LOCAL, PREFER_CLOUD)
        config: Optional configuration

    Returns:
        Selected BackendType

    Raises:
        BackendUnavailableError: If selected/policy backend is unavailable
    """
    selector = BackendSelector(config=config)
    return selector.select(backend=backend, policy=policy)
