"""JSON formatter for transcription results.

Produces structured JSON output with full metadata including:
- All transcription segments with timing and confidence
- Source media information
- Configuration used
- Processing duration
- Backend used

Example:
    >>> from audiocore.models import Segment, MediaInfo, TranscriptionResult, TranscriptionOptions
    >>> result = TranscriptionResult(
    ...     segments=[Segment(start_time=0.0, end_time=5.0, text="Hello")],
    ...     media_info=MediaInfo(...),
    ...     config_used=TranscriptionOptions(),
    ...     processing_time_seconds=5.0,
    ...     backend_used=BackendType.OPENAI
    ... )
    >>> json_output = format_json(result, TranscriptionOptions())
    >>> import json
    >>> data = json.loads(json_output)
    >>> data['segments'][0]['text']
    'Hello'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from audiocore.models.transcription import TranscriptionOptions, TranscriptionResult


def _serialize_value(value: Any) -> Any:
    """Convert non-JSON-serializable types to serializable equivalents.

    Handles:
    - Enum types (converted to string values)
    - Path objects (converted to strings)
    - Float infinity/nan (converted to None)

    Args:
        value: Any value that may need serialization.

    Returns:
        JSON-serializable equivalent of the value.
    """
    # Handle enum types (StrEnum and regular Enum)
    if hasattr(value, "value"):
        return value.value

    # Handle Path objects
    if isinstance(value, Path):
        return str(value)

    # Handle float special values
    if isinstance(value, float) and (
        value == float("inf") or value == float("-inf") or value != value
    ):  # noqa: SIM102
        return None

    return value


def _prepare_for_json(result: TranscriptionResult) -> dict[str, Any]:
    """Prepare TranscriptionResult for JSON serialization.

    Converts Pydantic models and handles non-serializable types.

    Args:
        result: TranscriptionResult to prepare.

    Returns:
        Dictionary ready for JSON serialization.
    """
    # Use model_dump() for Pydantic serialization
    data = result.model_dump()

    # Recursively process values to handle any non-serializable types (enums, paths, etc.)
    def process_dict(d: dict[str, Any]) -> dict[str, Any]:
        return {
            k: _serialize_value(v) if not isinstance(v, dict) else process_dict(v)
            for k, v in d.items()
        }

    return process_dict(data)


def format_json(
    result: TranscriptionResult, options: TranscriptionOptions, indent: int | None = 2
) -> str:
    """Format transcription result as structured JSON.

    Produces a JSON object containing:
    - segments: Array of all transcription segments with timing and text
    - media_info: Source media metadata
    - config_used: Configuration options used for transcription
    - processing_time_seconds: Processing duration
    - backend_used: Backend that performed the transcription

    All datetime, Path, and Enum types are converted to JSON-serializable
    types. UTF-8 encoding is guaranteed for all text content.

    Args:
        result: TranscriptionResult containing segments and metadata.
        options: TranscriptionOptions (included in output for reference).
        indent: Number of spaces for indentation. None for minified output.

    Returns:
        JSON string with full transcription result and metadata.

    Example:
        >>> result = TranscriptionResult(...)
        >>> json_str = format_json(result, TranscriptionOptions())
        >>> import json
        >>> data = json.loads(json_str)
        >>> print(json.dumps(data, indent=2))
        {
          "segments": [
            {"start_time": 0.0, "end_time": 5.0, "text": "Hello", "confidence": null}
          ],
          "media_info": {...},
          "config_used": {...},
          "processing_time_seconds": 5.0,
          "backend_used": "openai"
        }
    """
    data = _prepare_for_json(result)

    # ensure_ascii=False preserves UTF-8 characters
    return json.dumps(data, indent=indent, ensure_ascii=False)
