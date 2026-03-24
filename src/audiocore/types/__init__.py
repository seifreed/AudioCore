"""Type definitions for AudioCore.

This module provides typed enums for backend types, output formats,
error classifications, and selection policies with CLI/config compatibility.
"""

from audiocore.types.backend import BackendType, ModelSize, to_json_serializable
from audiocore.types.error import ModelErrorType
from audiocore.types.format import OutputFormat
from audiocore.types.policy import SelectionPolicy

__all__ = [
    "BackendType",
    "ModelSize",
    "ModelErrorType",
    "OutputFormat",
    "SelectionPolicy",
    "to_json_serializable",
]
