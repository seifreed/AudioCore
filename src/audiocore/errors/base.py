"""
Base exception classes for AudioCore.

This module provides the foundational exception hierarchy that all
AudioCore exceptions inherit from. Every exception includes:
- Unique error code (AUD-XXX)
- Human-readable message
- Context dictionary for debugging
- Actionable suggestions
"""

from typing import Any


class AudioCoreError(Exception):
    """
    Base exception for all AudioCore errors.

    All exceptions in AudioCore inherit from this class, providing:
    - Consistent error code format (AUD-XXX)
    - Actionable error messages
    - Context preservation for debugging
    - Suggestions for resolution

    Example:
        >>> try:
        ...     raise AudioCoreError("Something went wrong",
        ...                           context={"file": "audio.mp3"},
        ...                           suggestions=["Check file format"])
        ... except AudioCoreError as e:
        ...     print(f"[{e.error_code}] {e}")
        ...     print(f"Context: {e.context}")
        [AUD-000] Something went wrong
        Context: {'file': 'audio.mp3'}

    Attributes:
        error_code: Unique error code for this exception type (class attribute)
        message: Human-readable error description
        context: Dictionary of contextual information for debugging
        suggestions: List of actionable suggestions for resolution
    """

    # Default error code - subclasses should override
    error_code: str = "AUD-000"

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Initialize an AudioCore exception.

        Args:
            message: Human-readable error description
            context: Dictionary of contextual information (file paths, config values, etc.)
            suggestions: List of actionable suggestions for resolution
            cause: Original exception that caused this error (use `raise X from Y`)
        """
        super().__init__(message)

        # Store message for __str__
        self.message = message

        # Context dictionary for debugging (file paths, config values, etc.)
        self.context = context if context is not None else {}

        # Actionable suggestions for resolution
        self.suggestions = list(suggestions) if suggestions is not None else []

        # Store the original cause for programmatic access.
        # Do NOT set __cause__ here — Python's `raise X from Y` sets it
        # automatically after __init__, and an explicit assignment would
        # conflict with that mechanism.
        self.original_cause = cause

    def __str__(self) -> str:
        """Return the error message with optional context."""
        if self.context:
            context_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message

    def __repr__(self) -> str:
        """Return a detailed representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"context={self.context!r}, "
            f"suggestions={self.suggestions!r})"
        )

    def format_error(self) -> str:
        """
        Format the full error for display.

        Returns:
            A formatted string including error code, message, context, and suggestions.
        """
        lines = [f"[{self.error_code}] {self.message}"]

        if self.context:
            lines.append("Context:")
            for key, value in self.context.items():
                lines.append(f"  {key}: {value}")

        if self.suggestions:
            lines.append("Suggestions:")
            for i, suggestion in enumerate(self.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        return "\n".join(lines)
