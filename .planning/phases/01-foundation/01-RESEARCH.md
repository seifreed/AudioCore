# Phase 1: Foundation - Research

**Phase Goal**: Establish type-safe domain model and comprehensive error handling infrastructure

**Requirements**: CORE-01, CORE-02, ERR-01, ERR-02

---

## 1. Domain Analysis

### Core Domain Models (CORE-01)

Four primary models needed:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `TranscriptionOptions` | Configuration for transcription | language, model_size, backend, output_format |
| `Segment` | Single transcribed segment | start_time, end_time, text, confidence |
| `TranscriptionResult` | Complete transcription output | segments, media_info, config_used, timing |
| `MediaInfo` | Media file metadata | duration, format, codec, sample_rate, channels |

### Type Enums (CORE-02)

Five enums required:

| Enum | Values | Usage |
|------|--------|-------|
| `BackendType` | OPENAI, FASTER_WHISPER, AUTO | Backend selection |
| `OutputFormat` | TEXT, JSON, SRT, VTT | Output format choice |
| `ModelErrorType` | Various error classifications | Error categorization |
| `SelectionPolicy` | PREFER_LOCAL, PREFER_CLOUD, AUTO | Auto-selection logic |
| `ModelSize` | TINY, BASE, SMALL, MEDIUM, LARGE | Whisper model sizes |

### Exception Hierarchy (ERR-01)

```
AudioCoreError (base)
├── InputError
│   ├── InvalidInputError
│   └── MediaFormatError
├── ConfigurationError
│   └── InvalidConfigError
├── BackendError
│   ├── BackendUnavailableError
│   └── TranscriptionError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   └── APITimeoutError
└── ProcessingError
    └── VADError
```

### Error Context Preservation (ERR-02)

Each exception must carry:
- `error_code`: Unique string identifier
- `message`: User-friendly description
- `context`: Dict with file_path, operation, suggestions
- `__cause__`: Original exception (preserved)

---

## 2. Implementation Strategy

### Order of Implementation

1. **Exceptions first** (ERR-01, ERR-02) - Other modules will use these
2. **Type enums** (CORE-02) - Required by domain models
3. **Domain models** (CORE-01) - Depend on enums

### Rationale

- Exceptions are leaf modules with no dependencies on other project code
- Enums are imported by domain models
- Models import enums and may raise exceptions
- This ordering prevents circular imports

---

## 3. Technical Decisions

### Pydantic v2 Best Practices

| Decision | Rationale |
|----------|-----------|
| Use `BaseModel` with strict mode | Ensures validation runs on all inputs |
| Use `Field()` for constraints | Provides schema documentation |
| Use `model_validator` for cross-field validation | Complex validation logic |
| Use `ConfigDict(from_attributes=True)` | ORM compatibility if needed |
| Avoid `Any` type | Maintains full type safety |

### Exception Design Decisions

| Decision | Rationale |
|----------|-----------|
| Error codes as class attributes | Accessible without instance |
| `__str__` for user messages | Clean CLI output |
| `__repr__` for debugging | Include all context |
| `from` pattern for wrapping | Preserves traceback |
| `suggestions` as list in context | Multiple resolution options |

### Enum Design Decisions

| Decision | Rationale |
|----------|-----------|
| Inherit from `str, Enum` | JSON serializable, CLI compatible |
| Lowercase values | Case-insensitive matching |
| `@classmethod` for parsing | `BackendType.parse("openai")` |

---

## 4. Standard Patterns

### Pydantic v2 Model Pattern

```python
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class Segment(BaseModel):
    model_config = ConfigDict(
        strict=True,
        validate_assignment=True,
    )
    
    start_time: float = Field(..., ge=0.0, description="Start time in seconds")
    end_time: float = Field(..., ge=0.0, description="End time in seconds")
    text: str = Field(..., min_length=1, description="Transcribed text")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    
    @model_validator(mode='after')
    def validate_times(self) -> 'Segment':
        if self.end_time < self.start_time:
            raise ValueError('end_time must be >= start_time')
        return self
```

### Exception Pattern

```python
class AudioCoreError(Exception):
    error_code: str = "AUD-000"
    
    def __init__(
        self,
        message: str,
        context: Optional[dict] = None,
        suggestions: Optional[list[str]] = None,
    ):
        self.message = message
        self.context = context or {}
        if suggestions:
            self.context['suggestions'] = suggestions
        super().__init__(message)
    
    def __str__(self) -> str:
        return self.message
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.error_code!r}, context={self.context!r})"


class InvalidInputError(AudioCoreError):
    error_code = "AUD-001"
    
    def __init__(self, message: str, file_path: Optional[str] = None):
        context = {}
        if file_path:
            context['file_path'] = file_path
        suggestions = [
            "Verify the file exists and is readable",
            "Check the file format is supported",
        ]
        super().__init__(message, context, suggestions)
```

### Enum Pattern

```python
from enum import Enum

class BackendType(str, Enum):
    OPENAI = "openai"
    FASTER_WHISPER = "faster_whisper"
    AUTO = "auto"
    
    @classmethod
    def parse(cls, value: str) -> 'BackendType':
        normalized = value.lower().replace("-", "_")
        try:
            return cls(normalized)
        except ValueError:
            valid = [v.value for v in cls]
            raise ValueError(f"Invalid backend '{value}'. Valid options: {valid}")
```

---

## 5. Common Pitfalls

### Pydantic v2 Migration Issues

| Pitfall | Solution |
|---------|----------|
| `class Config` inner class | Use `model_config = ConfigDict(...)` |
| `@validator` decorator | Use `@field_validator` or `@model_validator` |
| `parse_obj()` deprecated | Use `model_validate()` |
| `.dict()` deprecated | Use `.model_dump()` |
| `Field(...)` without description | Always add description for IDE support |

### Exception Pitfalls

| Pitfall | Solution |
|---------|----------|
| Losing original traceback | Always use `raise Wrapper() from original` |
| Mutable default context | Use `None` default, create dict in `__init__` |
| Error codes as instance attributes | Define as class attribute |
| Missing error code | Use abstract property or base default |

### Enum Pitfalls

| Pitfall | Solution |
|---------|----------|
| Case-sensitive matching | Inherit from `str, Enum` and use `.lower()` |
| Invalid enum creation | Custom `parse()` method with helpful error |
| JSON serialization | `str, Enum` inheritance handles this |

---

## 6. Dependencies

### Required Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | ^2.0 | Domain models and validation |
| `typing_extensions` | ^4.0 | Python 3.14 type hints |

### Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Unit testing |
| `pytest-cov` | Coverage reporting |
| `mypy` | Type checking |
| `ruff` | Linting and formatting |

### Import Structure

```
src/audiocore/
├── __init__.py          # Public API exports
├── models/
│   ├── __init__.py      # Re-export all models
│   ├── segment.py       # Segment model
│   ├── transcription.py # TranscriptionOptions, TranscriptionResult
│   └── media.py         # MediaInfo model
├── types/
│   ├── __init__.py      # Re-export all enums
│   ├── backend.py       # BackendType enum
│   ├── format.py        # OutputFormat enum
│   ├── error.py         # ModelErrorType enum
│   └── policy.py        # SelectionPolicy enum
└── errors/
    ├── __init__.py      # Re-export all exceptions
    ├── base.py          # AudioCoreError base
    ├── input.py         # InputError, InvalidInputError, MediaFormatError
    ├── config.py        # ConfigurationError, InvalidConfigError
    ├── backend.py       # BackendError, BackendUnavailableError, TranscriptionError
    ├── api.py           # APIError, AuthenticationError, RateLimitError, APITimeoutError
    └── processing.py    # ProcessingError, VADError
```

---

## 7. Testing Strategy

### Unit Test Coverage

| Module | Test Focus |
|--------|------------|
| Enums | Valid value creation, invalid value rejection, parse method |
| Models | Valid instantiation, validation errors, serialization |
| Exceptions | Error codes, context preservation, suggestion inclusion |

### Test Patterns

```python
def test_segment_validates_times():
    with pytest.raises(ValidationError) as exc_info:
        Segment(start_time=10.0, end_time=5.0, text="test")
    
    error = exc_info.value.errors()[0]
    assert "end_time" in str(error).lower() or "greater" in str(error).lower()


def test_invalid_input_error_preserves_context():
    error = InvalidInputError("File not found", file_path="/path/to/file.mp3")
    
    assert error.error_code == "AUD-001"
    assert error.context["file_path"] == "/path/to/file.mp3"
    assert len(error.context["suggestions"]) > 0
    assert "AudioCoreError" in str(error.__repr__())


def test_backend_type_parse_case_insensitive():
    assert BackendType.parse("OpenAI") == BackendType.OPENAI
    assert BackendType.parse("faster-whisper") == BackendType.FASTER_WHISPER
    
    with pytest.raises(ValueError) as exc_info:
        BackendType.parse("invalid")
    
    assert "openai" in str(exc_info.value).lower()
```

### Test Organization

```
tests/
├── unit/
│   ├── models/
│   │   ├── test_segment.py
│   │   ├── test_transcription.py
│   │   └── test_media.py
│   ├── types/
│   │   ├── test_backend.py
│   │   ├── test_format.py
│   │   ├── test_error.py
│   │   └── test_policy.py
│   └── errors/
│       ├── test_base.py
│       ├── test_input.py
│       ├── test_config.py
│       ├── test_backend.py
│       ├── test_api.py
│       └── test_processing.py
└── conftest.py
```

---

## 8. File Structure Recommendations

### Recommended Package Structure

```
src/audiocore/
├── __init__.py
│   # Public exports:
│   # - All models: Segment, TranscriptionOptions, TranscriptionResult, MediaInfo
│   # - All types: BackendType, OutputFormat, ModelErrorType, SelectionPolicy, ModelSize
│   # - All errors: AudioCoreError and all subclasses
│
├── models/
│   ├── __init__.py
│   ├── segment.py
│   ├── transcription.py
│   └── media.py
│
├── types/
│   ├── __init__.py
│   ├── backend.py
│   ├── format.py
│   ├── error.py
│   └── policy.py
│
└── errors/
    ├── __init__.py
    ├── base.py
    ├── input.py
    ├── config.py
    ├── backend.py
    ├── api.py
    └── processing.py
```

### Module Content Summary

| Module | Classes/Functions | Lines (est.) |
|--------|-------------------|--------------|
| `models/segment.py` | `Segment` | 40 |
| `models/transcription.py` | `TranscriptionOptions`, `TranscriptionResult` | 80 |
| `models/media.py` | `MediaInfo` | 40 |
| `types/backend.py` | `BackendType` | 25 |
| `types/format.py` | `OutputFormat` | 20 |
| `types/error.py` | `ModelErrorType` | 30 |
| `types/policy.py` | `SelectionPolicy`, `ModelSize` | 25 |
| `errors/base.py` | `AudioCoreError` | 35 |
| `errors/input.py` | `InputError`, `InvalidInputError`, `MediaFormatError` | 50 |
| `errors/config.py` | `ConfigurationError`, `InvalidConfigError` | 30 |
| `errors/backend.py` | `BackendError`, `BackendUnavailableError`, `TranscriptionError` | 45 |
| `errors/api.py` | `APIError`, `AuthenticationError`, `RateLimitError`, `APITimeoutError` | 50 |
| `errors/processing.py` | `ProcessingError`, `VADError` | 25 |

**Total estimated lines: ~495**

---

## 9. Key Interfaces

### TranscriptionOptions

```python
class TranscriptionOptions(BaseModel):
    model_config = ConfigDict(strict=True)
    
    language: Optional[str] = Field(None, description="Language code (e.g., 'en', 'es')")
    model_size: ModelSize = Field(ModelSize.BASE, description="Whisper model size")
    backend: BackendType = Field(BackendType.AUTO, description="Backend selection")
    output_format: OutputFormat = Field(OutputFormat.TEXT, description="Output format")
    backend_preference: SelectionPolicy = Field(
        SelectionPolicy.AUTO, 
        description="Backend selection policy"
    )
```

### TranscriptionResult

```python
class TranscriptionResult(BaseModel):
    model_config = ConfigDict(strict=True)
    
    segments: list[Segment] = Field(..., description="Transcription segments")
    media_info: MediaInfo = Field(..., description="Source media information")
    config_used: TranscriptionOptions = Field(..., description="Configuration used")
    duration_seconds: float = Field(..., description="Processing duration")
    backend_used: BackendType = Field(..., description="Backend that processed")
```

---

## 10. Pre-Implementation Checklist

- [ ] Create `src/audiocore/` directory structure
- [ ] Create `pyproject.toml` with Pydantic v2 dependency
- [ ] Set up `pytest`, `mypy`, `ruff` configuration
- [ ] Implement error hierarchy (ERR-01, ERR-02)
- [ ] Implement type enums (CORE-02)
- [ ] Implement domain models (CORE-01)
- [ ] Write comprehensive unit tests
- [ ] Verify IDE autocomplete works
- [ ] Verify all exceptions have error codes
- [ ] Verify exception context preservation