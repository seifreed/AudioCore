"""Type definitions for AudioCore.

This module provides typed enums for backend types, output formats,
error classifications, and selection policies with CLI/config compatibility.
"""

from audiocore.types.backend import BackendType, ModelSize, to_json_serializable

__all__ = [
    "BackendType",
    "ModelSize",
    "to_json_serializable",
]
