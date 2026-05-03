"""Cancellation token for pipeline termination.

This module provides thread-safe cancellation support for the transcription
pipeline, allowing users to cancel long-running operations mid-execution.

Example:
    >>> token = CancellationToken()
    >>> # In another thread:
    >>> token.cancel()
    >>> # In pipeline:
    >>> token.check()  # Raises CancelledError if cancelled
"""

from __future__ import annotations

import threading

from audiocore.errors.base import AudioCoreError


class CancelledError(AudioCoreError):
    """Exception raised when pipeline is cancelled.

    Inherits from AudioCoreError so it carries error_code, context,
    and suggestions consistent with the rest of the error hierarchy.

    Note:
        Unlike Python's asyncio.CancelledError (which inherits from
        BaseException), this inherits from AudioCoreError (and therefore
        Exception). This means generic ``except Exception`` handlers will
        catch it. If you need to distinguish cancellation from other errors,
        catch CancelledError explicitly before the generic handler.

    Example:
        >>> try:
        ...     token.check()
        ... except CancelledError:
        ...     print("Pipeline cancelled")
    """

    def __init__(
        self,
        message: str = "Pipeline execution was cancelled",
        context: dict[str, object] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize CancelledError.

        Args:
            message: Human-readable cancellation message.
            context: Optional dict with diagnostic context.
            suggestions: Optional list of actionable suggestions.
        """
        super().__init__(
            message=message,
            error_code="AUD-500",
            context=context or {},
            suggestions=suggestions or ["Check if cancellation was intentional"],
        )


class CancellationToken:
    """Thread-safe token for pipeline cancellation.

    CancellationToken provides a thread-safe mechanism to signal
    cancellation across threads. The pipeline checks this token
    at stage boundaries and raises CancelledError if cancelled.

    Thread Safety:
        Uses threading.Event internally, which provides atomic
        operations for cancellation state.

    Example:
        >>> token = CancellationToken()
        >>>
        >>> # In pipeline thread:
        >>> token.check()  # Raises CancelledError if cancelled
        >>>
        >>> # In another thread:
        >>> token.cancel()
        >>>
        >>> # Check status:
        >>> if token.is_cancelled:
        ...     print("Cancelled!")
    """

    def __init__(self) -> None:
        """Initialize cancellation token (not cancelled by default)."""
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested.

        Thread-safe check that can be called from any thread.

        Returns:
            True if cancel() was called, False otherwise.
        """
        return self._event.is_set()

    def cancel(self) -> None:
        """Request cancellation of the pipeline.

        Thread-safe operation that signals all waiting threads.
        After calling cancel(), is_cancelled will return True
        and check() will raise CancelledError.

        This method is idempotent - calling it multiple times
        has no additional effect after the first call.
        """
        self._event.set()

    def check(self) -> None:
        """Check for cancellation and raise if cancelled.

        Raises:
            CancelledError: If cancellation was requested via cancel().

        This is the primary method for pipeline code to check for
        cancellation. Call it at stage boundaries or before
        long-running operations.

        Example:
            >>> token = CancellationToken()
            >>> try:
            ...     # Stage 1
            ...     token.check()
            ...     # Stage 2
            ...     token.check()
            ... except CancelledError:
            ...     # Handle cancellation
            ...     pass
        """
        if self._event.is_set():
            raise CancelledError()

    def reset(self) -> None:
        """Reset the cancellation token for reuse.

        After calling reset(), is_cancelled returns False and
        check() will not raise CancelledError until cancel()
        is called again.

        Thread-safe operation that clears the internal event.
        """
        self._event.clear()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait for cancellation request.

        Thread-safe blocking operation that waits until cancel()
        is called or timeout expires.

        Args:
            timeout: Maximum time to wait in seconds.
                None means wait indefinitely.

        Returns:
            True if cancelled within timeout, False if timeout expired.

        Example:
            >>> token = CancellationToken()
            >>> # In another thread: token.cancel()
            >>> cancelled = token.wait(timeout=5.0)
            >>> if cancelled:
            ...     print("Was cancelled")
        """
        return self._event.wait(timeout=timeout)
