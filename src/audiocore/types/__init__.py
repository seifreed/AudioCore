"""Type definitions for AudioCore.

This module provides typed enums for backend types, output formats,
and selection policies with CLI/config compatibility.
"""

from audiocore.types.backend import BackendType, ModelSize, to_json_serializable
from audiocore.types.format import OutputFormat
from audiocore.types.policy import SelectionPolicy
from audiocore.types.task import TranscriptionTask

__all__ = [
    "BackendType",
    "ModelSize",
    "OutputFormat",
    "SelectionPolicy",
    "TranscriptionTask",
    "to_json_serializable",
]
