"""Tests for cancellation token and CancelledError.

This module tests the cancellation system including:
- CancellationToken state management
- Thread-safe cancellation
- CancelledError exception behavior
"""

from __future__ import annotations

import threading
import time

import pytest

from audiocore.errors.base import AudioCoreError
from audiocore.pipeline.cancellation import CancellationToken, CancelledError


class TestCancelledError:
    """Tests for CancelledError exception."""

    def test_cancelled_error_is_audio_core_error(self) -> None:
        """CancelledError inherits from AudioCoreError."""
        assert issubclass(CancelledError, AudioCoreError)
        assert issubclass(CancelledError, Exception)

    def test_cancelled_error_default_message(self) -> None:
        """CancelledError has default message."""
        exc = CancelledError()
        assert exc.message == "Pipeline execution was cancelled"
        assert str(exc) == "Pipeline execution was cancelled"
        assert "[AUD-500]" in exc.format_error()

    def test_cancelled_error_custom_message(self) -> None:
        """CancelledError can have custom message."""
        exc = CancelledError("Custom cancellation message")
        assert exc.message == "Custom cancellation message"
        assert "Custom cancellation message" in str(exc)

    def test_cancelled_error_error_code(self) -> None:
        """CancelledError has AUD-500 error code."""
        exc = CancelledError()
        assert exc.error_code == "AUD-500"

    def test_cancelled_error_context(self) -> None:
        """CancelledError has empty context."""
        exc = CancelledError()
        assert exc.context == {}

    def test_cancelled_error_suggestions(self) -> None:
        """CancelledError has actionable suggestions."""
        exc = CancelledError()
        assert len(exc.suggestions) == 3
        assert "cancellation was intentional" in exc.suggestions[0].lower()
        assert "new CancellationToken" in exc.suggestions[1]
        assert "partial results" in exc.suggestions[2].lower()

    def test_cancelled_error_is_exception(self) -> None:
        """CancelledError can be caught as Exception."""
        try:
            raise CancelledError()
        except Exception as exc:
            assert isinstance(exc, CancelledError)

    def test_cancelled_error_raises_correctly(self) -> None:
        """CancelledError can be raised and caught."""
        with pytest.raises(CancelledError):
            raise CancelledError("Test cancellation")


class TestCancellationToken:
    """Tests for CancellationToken class."""

    def test_token_not_cancelled_by_default(self) -> None:
        """New token is not cancelled."""
        token = CancellationToken()
        assert token.is_cancelled is False

    def test_token_cancel_sets_is_cancelled(self) -> None:
        """cancel() sets is_cancelled to True."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

    def test_token_check_raises_when_cancelled(self) -> None:
        """check() raises CancelledError when cancelled."""
        token = CancellationToken()
        token.cancel()

        with pytest.raises(CancelledError) as exc_info:
            token.check()

        assert exc_info.value.error_code == "AUD-500"

    def test_token_check_does_not_raise_when_not_cancelled(self) -> None:
        """check() does not raise when not cancelled."""
        token = CancellationToken()

        # Should not raise
        token.check()

    def test_token_cancel_is_idempotent(self) -> None:
        """Calling cancel() multiple times has no additional effect."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

        token.cancel()  # Second call
        assert token.is_cancelled is True

        token.cancel()  # Third call
        assert token.is_cancelled is True

    def test_token_can_be_reset(self) -> None:
        """reset() clears cancellation state."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

        token.reset()
        assert token.is_cancelled is False

    def test_token_check_after_reset(self) -> None:
        """check() does not raise after reset()."""
        token = CancellationToken()
        token.cancel()
        token.reset()

        # Should not raise after reset
        token.check()

    def test_token_reset_before_cancel(self) -> None:
        """reset() before cancel() is safe."""
        token = CancellationToken()
        token.reset()  # No-op, should be fine

        assert token.is_cancelled is False


class TestCancellationTokenThreadSafety:
    """Tests for thread-safe cancellation."""

    def test_cancel_from_another_thread(self) -> None:
        """CancellationToken can be cancelled from another thread."""
        token = CancellationToken()

        def cancel_after_delay() -> None:
            time.sleep(0.01)
            token.cancel()

        thread = threading.Thread(target=cancel_after_delay)
        thread.start()

        # Wait for cancellation
        cancelled = token.wait(timeout=1.0)
        assert cancelled is True
        assert token.is_cancelled is True

        thread.join()

    def test_check_raises_from_another_thread(self) -> None:
        """check() raises CancelledError when cancelled from another thread."""
        token = CancellationToken()
        check_raised = threading.Event()
        exception_caught = threading.Event()

        def cancel_and_check() -> None:
            # Cancel after a brief delay
            token.cancel()
            time.sleep(0.01)

            # Try to check (should raise)
            try:
                token.check()
            except CancelledError:
                check_raised.set()

        thread = threading.Thread(target=cancel_and_check)
        thread.start()

        # Wait for completion
        check_raised.wait(timeout=1.0)
        assert check_raised.is_set() is True

        thread.join()

    def test_multiple_threads_can_check(self) -> None:
        """Multiple threads can check cancellation simultaneously."""
        token = CancellationToken()
        results: list[bool] = []
        errors: list[Exception | None] = []
        lock = threading.Lock()

        def check_and_record() -> None:
            try:
                token.check()
                with lock:
                    results.append(False)
                    errors.append(None)
            except CancelledError as exc:
                with lock:
                    results.append(True)
                    errors.append(exc)

        # Create multiple threads
        threads = [threading.Thread(target=check_and_record) for _ in range(5)]

        # Cancel before threads start
        token.cancel()

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=1.0)

        # All threads should have caught CancelledError
        assert len(results) == 5
        assert all(results)
        assert all(errors)

    def test_wait_blocks_until_cancelled(self) -> None:
        """wait() blocks until cancel() is called."""
        token = CancellationToken()
        wait_start = time.time()
        thread_started = threading.Event()

        def cancel_after_delay() -> None:
            thread_started.set()
            time.sleep(0.05)
            token.cancel()

        thread = threading.Thread(target=cancel_after_delay)
        thread.start()

        thread_started.wait(timeout=1.0)

        # This should block until cancelled
        cancelled = token.wait(timeout=1.0)
        wait_duration = time.time() - wait_start

        assert cancelled is True
        assert wait_duration >= 0.05  # Waited at least until cancel

        thread.join()

    def test_wait_timeout_expires(self) -> None:
        """wait() returns False if timeout expires without cancellation."""
        token = CancellationToken()

        start = time.time()
        cancelled = token.wait(timeout=0.05)
        duration = time.time() - start

        assert cancelled is False
        assert duration >= 0.05  # Waited the full timeout

    def test_reset_from_another_thread(self) -> None:
        """reset() can be called from another thread."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled is True

        def reset_token() -> None:
            token.reset()

        thread = threading.Thread(target=reset_token)
        thread.start()
        thread.join()

        assert token.is_cancelled is False


class TestCancellationTokenUsage:
    """Tests for typical usage patterns."""

    def test_pipeline_cancellation_pattern(self) -> None:
        """Test typical pipeline cancellation pattern."""
        token = CancellationToken()

        # Simulate stage progression
        stages: list[str] = []

        # Stage 1: Probing
        token.check()
        stages.append("probing")

        # Stage 2: Extracting
        token.check()
        stages.append("extracting")

        # Cancel before VAD
        token.cancel()

        # Stage 3: VAD should fail
        with pytest.raises(CancelledError):
            token.check()

        # Only first two stages completed
        assert stages == ["probing", "extracting"]

    def test_reset_and_reuse(self) -> None:
        """CancellationToken can be reset and reused."""
        token = CancellationToken()

        # First use
        token.cancel()
        assert token.is_cancelled is True
        with pytest.raises(CancelledError):
            token.check()

        # Reset for second use
        token.reset()
        assert token.is_cancelled is False
        token.check()  # No error

        # Second use
        token.cancel()
        assert token.is_cancelled is True
        with pytest.raises(CancelledError):
            token.check()

    def test_is_cancelled_property_is_threadsafe(self) -> None:
        """is_cancelled property can be read from multiple threads."""
        token = CancellationToken()
        results: list[bool] = []
        lock = threading.Lock()

        def check_is_cancelled() -> None:
            with lock:
                results.append(token.is_cancelled)

        # Read multiple times before cancellation
        threads = [threading.Thread(target=check_is_cancelled) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=1.0)

        token.cancel()

        # Read multiple times after cancellation
        threads = [threading.Thread(target=check_is_cancelled) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=1.0)

        # Before: all False, After: all True
        assert results[:3] == [False, False, False]
        assert results[3:] == [True, True, True]

    def test_multiple_consecutive_cancels(self) -> None:
        """Multiple consecutive cancels are idempotent."""
        token = CancellationToken()

        for _ in range(10):
            token.cancel()
            assert token.is_cancelled is True

    def test_multiple_consecutive_resets(self) -> None:
        """Multiple consecutive resets are idempotent."""
        token = CancellationToken()
        token.cancel()

        for _ in range(10):
            token.reset()
            assert token.is_cancelled is False
