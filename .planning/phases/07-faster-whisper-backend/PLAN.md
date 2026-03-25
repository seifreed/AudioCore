---
phase: 07-faster-whisper-backend
type: phase-plan
created: 2026-03-25
status: planning
requirements:
  - FAUX-01  # Faster-Whisper Integration
  - FAUX-02  # Faster-Whisper Configuration
  - FAUX-03  # Model Management
---

# Phase 7: Faster-Whisper Backend

## Phase Goal

Implement high-quality local transcription using faster-whisper (CTranslate2) with automatic model management, GPU acceleration, and comprehensive configuration support.

**Purpose:** Enable offline transcription with faster-whisper as an alternative to cloud-based OpenAI Whisper API, providing users with privacy, cost savings, and no external API dependencies.

**Output:** FasterWhisperBackend implementing TranscriptionBackend ABC with model management CLI/API support.

## Dependencies

### Cross-Phase Dependencies

```
Phase 1 (Foundation) ──► Phase 7
  - AudioCoreError, BackendError, TranscriptionError
  - BackendType.FASTER_WHISPER enum
  - ModelSize enum (tiny/base/small/medium/large)
  - Segment, MediaInfo, TranscriptionOptions, TranscriptionResult

Phase 2 (Configuration) ──► Phase 7
  - AppConfig pattern with pydantic-settings
  - Environment variable configuration (AUDIOCORE_* prefix)
  - SecretStr for sensitive data (not needed here, but pattern reference)

Phase 5 (Backend Abstraction) ──► Phase 7
  - TranscriptionBackend ABC
  - BackendRegistry singleton pattern
  - is_backend_available helper
```

### External Dependencies (NEW)

- `faster-whisper>=1.0.0` - CTranslate2-based Whisper implementation
- `huggingface-hub>=0.20.0` - Model download from HuggingFace Hub
- Optional: `torch>=2.0.0` - For GPU device detection (not for transcription itself)

### Internal File Dependencies

```
src/audiocore/types/backend.py ──► BackendType enum
src/audiocore/models/__init__.py ──► All domain models
src/audiocore/errors/backend.py ──► BackendError, TranscriptionError
src/audiocore/backends/base.py ──► TranscriptionBackend ABC
src/audiocore/backends/registry.py ──► BackendRegistry pattern
src/audiocore/config/app_config.py ──► AppConfig integration pattern
```

## Goal-Backward Analysis

### Goal Statement

User can transcribe audio locally using faster-whisper with automatic model management, GPU acceleration, and configurable parameters.

### Observable Truths (What must be TRUE for goal achievement)

1. **Model Availability:** User can list available and downloaded models
2. **Model Download:** Models download automatically from HuggingFace on first use
3. **Model Caching:** Downloaded models persist in local cache for offline use
4. **Device Selection:** Backend automatically selects best device (CUDA/MPS/CPU)
5. **Transcription:** User can transcribe audio files with timestamps and segments
6. **Configuration:** User can configure model size, device, beam size, language via config
7. **Availability Check:** is_available() returns True when dependencies installed and model ready
8. **Error Handling:** All faster-whisper errors map to AudioCore exception hierarchy

### Required Artifacts

| Artifact | Purpose | Min Lines | Key Exports |
|----------|---------|-----------|-------------|
| `src/audiocore/config/faster_whisper_config.py` | Configuration model | 80 | `FasterWhisperConfig` |
| `src/audiocore/backends/faster_whisper/model_manager.py` | Model download/cache management | 150 | `ModelManager`, `ModelInfo` |
| `src/audiocore/backends/faster_whisper/device.py` | GPU device detection | 60 | `get_best_device`, `DeviceType` |
| `src/audiocore/backends/faster_whisper_backend.py` | Backend implementation | 300 | `FasterWhisperBackend` |
| `tests/unit/backends/test_faster_whisper_backend.py` | Unit tests | 400 | Test classes |
| `tests/unit/backends/test_model_manager.py` | Model manager tests | 200 | Test classes |
| `tests/integration/test_faster_whisper_integration.py` | Integration tests | 150 | Integration tests |

### Required Wiring

```yaml
key_links:
  - from: "FasterWhisperBackend"
    to: "TranscriptionBackend ABC"
    via: "inheritance"
    pattern: "class FasterWhisperBackend(TranscriptionBackend)"
    
  - from: "FasterWhisperBackend.transcribe()"
    to: "faster_whisper.WhisperModel"
    via: "model instantiation and transcribe() call"
    pattern: "WhisperModel(audio_path, device, compute_type).transcribe()"
    
  - from: "ModelManager"
    to: "HuggingFace Hub"
    via: "huggingface_hub.hf_hub_download"
    pattern: "hf_hub_download(repo_id, filename, cache_dir)"
    
  - from: "FasterWhisperConfig"
    to: "AppConfig"
    via: "Nested settings field"
    pattern: "class AppConfig(BaseSettings): faster_whisper: FasterWhisperConfig"
    
  - from: "BackendRegistry"
    to: "FasterWhisperBackend"
    via: "register() call"
    pattern: "register(BackendType.FASTER_WHISPER, FasterWhisperBackend)"
```

## Plan Breakdown

### Plan 07-01: Model Manager and Configuration

**Objective:** Implement model download, caching, and configuration infrastructure.

**Wave:** 1 (No dependencies on other Phase 7 plans)

**Autonomous:** true

**Requirements:** FAUX-02 (partial), FAUX-03

**Files Modified:**
- `src/audiocore/config/faster_whisper_config.py` (new)
- `src/audiocore/backends/faster_whisper/__init__.py` (new)
- `src/audiocore/backends/faster_whisper/model_manager.py` (new)
- `src/audiocore/backends/faster_whisper/device.py` (new)

---

### Plan 07-02: FasterWhisperBackend Implementation

**Objective:** Implement TranscriptionBackend ABC with faster-whisper integration.

**Wave:** 2 (Depends on Plan 07-01 for config and model manager)

**Autonomous:** true

**Requirements:** FAUX-01 (primary)

**Files Modified:**
- `src/audiocore/backends/faster_whisper_backend.py` (new)
- `src/audiocore/backends/__init__.py` (modified)
- `tests/unit/backends/test_faster_whisper_backend.py` (new)

---

### Plan 07-03: Integration and Registry

**Objective:** Register backend, integration tests, and end-to-end validation.

**Wave:** 3 (Depends on Plan 07-02)

**Autonomous:** true

**Requirements:** FAUX-01 (validation), FAUX-02 (validation), FAUX-03 (validation)

**Files Modified:**
- `tests/integration/test_faster_whisper_integration.py` (new)
- Integration with existing test infrastructure

---

## Execution Context

<execution_context>
@/Users/seifreed/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/seifreed/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

## Context Files

<context>
@/Users/seifreed/tools/personal/AudioCore/.planning/PROJECT.md
@/Users/seifreed/tools/personal/AudioCore/.planning/ROADMAP.md
@/Users/seifreed/tools/personal/AudioCore/.planning/STATE.md
</context>

## Interface Contracts

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From `src/audiocore/backends/base.py`:
```python
class TranscriptionBackend(abc.ABC):
    @property
    @abc.abstractmethod
    def backend_type(self) -> BackendType: ...
    
    @abc.abstractmethod
    def transcribe(self, audio_path: Path | str, options: TranscriptionOptions) -> TranscriptionResult: ...
    
    @abc.abstractmethod
    def get_name(self) -> str: ...
    
    @abc.abstractmethod
    def is_available(self) -> bool: ...
    
    @abc.abstractmethod
    def get_model_options(self) -> list[str]: ...
```

From `src/audiocore/types/backend.py`:
```python
class BackendType(str, Enum):
    OPENAI = "openai"
    FASTER_WHISPER = "faster_whisper"
    AUTO = "auto"
```

From `src/audiocore/types/backend.py`:
```python
class ModelSize(str, Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
```

From `src/audiocore/models/transcription.py`:
```python
class TranscriptionOptions(BaseModel):
    model_size: ModelSize = ModelSize.BASE
    language: str | None = None
    output_format: OutputFormat = OutputFormat.JSON
    # ... other fields
```

From `src/audiocore/errors/backend.py`:
```python
class BackendError(AudioCoreError):
    error_code: str = "AUD-200"
    
class BackendUnavailableError(BackendError):
    error_code: str = "AUD-201"
    
class TranscriptionError(BackendError):
    error_code: str = "AUD-202"
```

From `src/audiocore/backends/registry.py`:
```python
class BackendRegistry:
    def register(self, backend_type: BackendType, backend_class: type[TranscriptionBackend]) -> None: ...
    def get_backend(self, backend_type: BackendType) -> TranscriptionBackend: ...
    def list_backends(self) -> list[BackendType]: ...
    def is_available(self, backend_type: BackendType) -> bool: ...
```

From `src/audiocore/config/openai_config.py` (pattern reference):
```python
class OpenAIConfig(BaseSettings):
    api_key: SecretStr | None = None
    timeout: int = 300
    max_retries: int = 2
    organization: str | None = None
    base_url: str | None = None
    
    @field_validator("api_key")
    def validate_api_key(cls, v): ...
```
</interfaces>

## Verification Criteria

### Per-Plan Verification

**Plan 07-01:**
- [ ] FasterWhisperConfig validates all fields correctly
- [ ] Device detection returns "cuda", "mps", or "cpu" based on availability
- [ ] ModelManager.download_model() creates cache directory and downloads from HuggingFace
- [ ] ModelManager.list_models() returns available and downloaded models
- [ ] ModelManager.get_model_path() returns local path or downloads if not cached
- [ ] All unit tests pass with >95% coverage

**Plan 07-02:**
- [ ] FasterWhisperBackend implements all TranscriptionBackend ABC methods
- [ ] transcribe() returns TranscriptionResult with segments and timestamps
- [ ] is_available() returns True when faster-whisper installed
- [ ] Lazy model loading (model created on first transcribe() call)
- [ ] All faster-whisper exceptions mapped to AudioCore exceptions
- [ ] Configuration parameters passed to WhisperModel correctly
- [ ] All unit tests pass with mocked faster-whisper (no model download)

**Plan 07-03:**
- [ ] Backend registered in BackendRegistry
- [ ] Integration test transcribes real audio file successfully
- [ ] Model auto-download works on first use
- [ ] GPU acceleration works when available
- [ ] CPU fallback works when no GPU available
- [ ] All integration tests pass (may be skipped if no models cached)

### Phase Success Criteria

**Goal Achievement:** User can transcribe audio locally using faster-whisper with automatic model management.

**Measurable Truths:**
1. ✅ `FasterWhisperBackend().is_available()` returns True when dependencies installed
2. ✅ `FasterWhisperBackend().transcribe("audio.mp3", options)` returns TranscriptionResult
3. ✅ Models download automatically from HuggingFace on first use
4. ✅ Downloaded models cached in `~/.cache/huggingface/hub` (or configured path)
5. ✅ `ModelManager.list_models()` shows available and downloaded models
6. ✅ GPU acceleration (CUDA/MPS) selected automatically when available
7. ✅ CPU fallback works reliably
8. ✅ All errors mapped to AudioCore exception hierarchy with actionable suggestions
9. ✅ Backend registered and discoverable via `BackendRegistry.list_backends()`
10. ✅ Configuration via `AppConfig.faster_whisper` or environment variables

**Coverage Requirements:**
- Unit tests: >95% coverage for all new modules
- Integration tests: At least 1 real transcription (may use tiny model for speed)
- Error handling tests: All exception paths covered

## Risk Mitigation

### Phase Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| faster-whisper dependency issues | Low | High | Add version constraint, test on CI |
| HuggingFace Hub download failures | Medium | Medium | Retry logic, offline mode detection |
| GPU compatibility (CUDA/MPS) | Medium | Medium | Extensive device detection, CPU fallback guaranteed |
| Model size disk usage | Low | Low | Document disk requirements, add cache management API |
| Memory usage for large models | Medium | Medium | Document memory requirements, suggest smaller models |

### Technical Considerations

1. **Model Format:** faster-whisper uses CTranslate2-optimized models, not original Whisper
   - Models: `guillaumekln/faster-whisper-{size}`
   - Smaller models (tiny/base) for testing, larger for production
   
2. **Device Detection Priority:** CUDA > MPS > CPU
   - Handle CUDA not available gracefully
   - Handle MPS (Apple Silicon) detection correctly
   
3. **Cache Directory:** Use HuggingFace default `~/.cache/huggingface/hub`
   - Allow override via configuration
   
4. **Lazy Loading:** Model should load on first transcribe() call
   - Avoid long startup times
   - Check availability without loading model

5. **Error Mapping:** Map faster-whisper exceptions to AudioCore hierarchy
   - `transcribe()` errors → TranscriptionError
   - Model load errors → BackendUnavailableError
   - Device errors → BackendError

## Implementation Notes

### Pattern Consistency (from Phase 06)

Follow OpenAIBackend patterns:
- Lazy initialization in `_get_client()` equivalent (model loading)
- Comprehensive error handling with mapped exceptions
- File validation before processing
- Duration extraction from result
- Thread-safe singleton pattern (if multiple instances problematic)

### Configuration Pattern

Follow OpenAIConfig pattern:
- Separate config class, not inline in backend
- Pydantic validation for all fields
- Integration with AppConfig via nested field
- Environment variable support via pydantic-settings

### Model Manager Pattern

New pattern for model management:
- Singleton class for model cache management
- Thread-safe model loading
- HuggingFace Hub integration
- Cache directory management
- Model listing and deletion

## Next Steps

After planning approval:
1. Execute Plan 07-01 (Model Manager and Configuration)
2. Execute Plan 07-02 (FasterWhisperBackend Implementation)
3. Execute Plan 07-03 (Integration and Registry)
4. Verify all success criteria met
5. Update STATE.md with completion notes