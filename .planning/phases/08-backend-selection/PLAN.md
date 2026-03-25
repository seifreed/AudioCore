---
phase: 08-backend-selection
type: phase-plan
created: 2026-03-25
status: planning
requirements:
  - SEL-01  # Automatic Backend Selection
  - SEL-02  # Backend Availability Checks
  - SEL-03  # Explicit Backend Selection
---

# Phase 8: Backend Selection

## Phase Goal

Implement intelligent backend selection with automatic policy-based fallback and explicit user override, enabling seamless switching between local and cloud transcription based on availability, cost, and user preferences.

**Purpose:** Provide abstraction over backend choice so users don't have to decide between OpenAI and faster-whisper — the system automatically selects the best available backend or follows explicit configuration.

**Output:** BackendSelector with policy-based selection, BackendAvailabilityChecker for fast pre-flight checks, and integration with TranscriptionOptions for explicit override.

## Dependencies

### Cross-Phase Dependencies

```
Phase 1 (Foundation) ──► Phase 8
  - AudioCoreError, BackendUnavailableError, TranscriptionError
  - BackendType enum (OPENAI, FASTER_WHISPER, AUTO)
  - SelectionPolicy enum (PREFER_LOCAL, PREFER_CLOUD, AUTO)

Phase 5 (Backend Abstraction) ──► Phase 8
  - TranscriptionBackend ABC (backend_type, is_available, get_name)
  - BackendRegistry singleton (register, get_backend, is_available, list_backends)
  - is_backend_available helper

Phase 6 (OpenAI Backend) ──► Phase 8
  - OpenAIBackend implementation
  - OpenAIConfig with api_key validation

Phase 7 (Faster-Whisper Backend) ──► Phase 8
  - FasterWhisperBackend implementation
  - FasterWhisperConfig with model/device settings
  - ModelManager for download status
```

### Internal File Dependencies

```
src/audiocore/types/backend.py ──► BackendType enum
src/audiocore/types/policy.py ──► SelectionPolicy enum
src/audiocore/backends/base.py ──► TranscriptionBackend ABC
src/audiocore/backends/registry.py ──► BackendRegistry
src/audiocore/config/app_config.py ──► AppConfig integration
src/audiocore/models/transcription.py ──► TranscriptionOptions
```

## Goal-Backward Analysis

### Goal Statement

User can transcribe audio using auto-selected backend with policy-based fallback, or explicitly specify backend, and the system transparently handles availability without API calls for local backends.

### Observable Truths (What must be TRUE for goal achievement)

1. **AUTO Policy:** System selects fastest available backend automatically
2. **PREFER_LOCAL:** System uses faster-whisper when available, falls back to OpenAI only if local unavailable
3. **PREFER_CLOUD:** System uses OpenAI when API key present, falls back to faster-whisper only if no API key
4. **Explicit Selection:** User can override policy with backend parameter (CLI/API)
5. **Availability Check:** Local backend availability check completes in <1s with no network calls
6. **Cloud Availability:** OpenAI availability check validates API key presence without API call
7. **Error Messages:** Unavailable backend selection raises clear error with actionable guidance
8. **Backend Status:** User can query which backends are available and why

### Required Artifacts

| Artifact | Purpose | Min Lines | Key Exports |
|----------|---------|-----------|-------------|
| `src/audiocore/backends/availability.py` | Backend availability checking | 100 | `BackendAvailabilityChecker`, `BackendStatus` |
| `src/audiocore/backends/selector.py` | Policy-based backend selection | 250 | `BackendSelector`, `select_backend` |
| `tests/unit/backends/test_availability.py` | Availability unit tests | 200 | Test classes |
| `tests/unit/backends/test_selector.py` | Selector unit tests | 300 | Test classes |

### Required Wiring

```yaml
key_links:
  - from: "BackendAvailabilityChecker"
    to: "BackendRegistry"
    via: "list_backends, is_available"
    pattern: "registry.list_backends() -> check each is_available()"
    
  - from: "BackendAvailabilityChecker"
    to: "TranscriptionBackend"
    via: "is_available method"
    pattern: "backend.is_available() returns True/False"
    
  - from: "BackendSelector"
    to: "BackendAvailabilityChecker"
    via: "get_available_backends"
    pattern: "checker.get_available_backends() -> BackendStatus[]"
    
  - from: "BackendSelector"
    to: "SelectionPolicy"
    via: "policy parameter"
    pattern: "apply_policy(available, policy) -> BackendType"
    
  - from: "select_backend"
    to: "BackendRegistry"
    via: "get_backend"
    pattern: "registry.get_backend(selected_type) -> TranscriptionBackend"
    
  - from: "TranscriptionOptions"
    to: "BackendSelector"
    via: "backend + backend_preference fields"
    pattern: "select_backend(options.backend, options.backend_preference)"
```

## Plan Breakdown

### Plan 08-01: Backend Availability Checker

**Objective:** Implement fast availability checking for all backends with status reporting.

**Wave:** 1 (Foundation layer, no dependencies on other Phase 8 plans)

**Autonomous:** true

**Requirements:** SEL-02

**Files Modified:**
- `src/audiocore/backends/availability.py` (new)
- `src/audiocore/backends/__init__.py` (modified)
- `tests/unit/backends/test_availability.py` (new)

---

### Plan 08-02: Policy-Based Backend Selector

**Objective:** Implement intelligent backend selection with policy support and explicit override.

**Wave:** 2 (Depends on Plan 08-01 for availability checking)

**Autonomous:** true

**Requirements:** SEL-01, SEL-03

**Files Modified:**
- `src/audiocore/backends/selector.py` (new)
- `src/audiocore/backends/__init__.py` (modified)
- `tests/unit/backends/test_selector.py` (new)

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

From `src/audiocore/types/policy.py`:
```python
class SelectionPolicy(str, Enum):
    PREFER_LOCAL = "prefer_local"  # Use local if available, else cloud
    PREFER_CLOUD = "prefer_cloud"  # Use cloud if API key, else local
    AUTO = "auto"  # Select fastest available
```

From `src/audiocore/types/backend.py`:
```python
class BackendType(str, Enum):
    OPENAI = "openai"
    FASTER_WHISPER = "faster_whisper"
    AUTO = "auto"  # Automatic selection
```

From `src/audiocore/backends/base.py`:
```python
class TranscriptionBackend(abc.ABC):
    @property
    @abc.abstractmethod
    def backend_type(self) -> BackendType: ...
    
    @abc.abstractmethod
    def is_available(self) -> bool: ...
    
    @abc.abstractmethod
    def transcribe(self, audio_path: Path | str, options: TranscriptionOptions) -> TranscriptionResult: ...
```

From `src/audiocore/backends/registry.py`:
```python
class BackendRegistry:
    def register(self, backend_type: BackendType, backend_class: type[TranscriptionBackend]) -> None: ...
    def get_backend(self, backend_type: BackendType) -> TranscriptionBackend: ...
    def list_backends(self) -> list[BackendType]: ...
    def is_available(self, backend_type: BackendType) -> bool: ...
    def clear(self) -> None: ...  # For testing
```

From `src/audiocore/models/transcription.py`:
```python
class TranscriptionOptions(BaseModel):
    backend: BackendType = BackendType.AUTO
    backend_preference: SelectionPolicy = SelectionPolicy.AUTO
    # ... other fields
```

From `src/audiocore/errors/backend.py`:
```python
class BackendError(AudioCoreError):
    error_code: str = "AUD-200"

class BackendUnavailableError(BackendError):
    error_code: str = "AUD-201"
```

From `src/audiocore/config/openai_config.py`:
```python
class OpenAIConfig(BaseSettings):
    api_key: SecretStr | None = None
    # API key check: config.api_key is not None (SecretStr)
```

From `src/audiocore/config/faster_whisper_config.py` (Phase 7):
```python
class FasterWhisperConfig(BaseSettings):
    model_size: ModelSize = ModelSize.BASE
    device: str | None = None  # None = auto-detect
    # Availability check: faster-whisper installed, model downloaded or can download
```
</interfaces>

## Verification Criteria

### Per-Plan Verification

**Plan 08-01:**
- [ ] BackendStatus dataclass captures backend type, availability, reason if unavailable
- [ ] BackendAvailabilityChecker.get_available_backends() returns list[BackendStatus]
- [ ] Local backend check (faster-whisper) completes in <1s without network calls
- [ ] Cloud backend check (OpenAI) checks API key presence without API call
- [ ] All backends checkable regardless of registration status
- [ ] All unit tests pass with >95% coverage

**Plan 08-02:**
- [ ] BackendSelector implements all three policies (AUTO, PREFER_LOCAL, PREFER_CLOUD)
- [ ] AUTO policy selects fastest available backend (CUDA > MPS > CPU > Cloud for small files)
- [ ] PREFER_LOCAL uses faster-whisper if available, falls back to OpenAI
- [ ] PREFER_CLOUD uses OpenAI if API key present, falls back to faster-whisper
- [ ] Explicit backend override (BackendType.OPENAI or FASTER_WHISPER) bypasses policy
- [ ] BackendType.AUTO with explicit selection raises clear error
- [ ] Unavailable backend raises BackendUnavailableError with actionable message
- [ ] BackendSelector integrated with BackendRegistry
- [ ] All unit tests pass with >95% coverage

### Phase Success Criteria

**Goal Achievement:** User can select backend by policy or explicit choice with transparent availability handling.

**Measurable Truths:**
1. ✅ `BackendAvailabilityChecker.get_available_backends()` returns status for all registered backends
2. ✅ Local backend availability check completes in <1s without network calls
3. ✅ Cloud backend check validates API key without making API calls
4. ✅ `BackendSelector.select()` with AUTO policy returns fastest available backend
5. ✅ `BackendSelector.select()` with PREFER_LOCAL returns faster-whisper if available
6. ✅ `BackendSelector.select()` with PREFER_CLOUD returns OpenAI if API key present
7. ✅ Explicit `BackendType.OPENAI` selection succeeds when API key present
8. ✅ Explicit `BackendType.OPENAI` raises BackendUnavailableError when API key missing
9. ✅ Each unavailable backend provides clear reason ("API key not set", "faster-whisper not installed")
10. ✅ BackendSelector works with BackendRegistry to retrieve actual backend instance

**Coverage Requirements:**
- Unit tests: >95% coverage for all new modules
- Policy behavior tests: All three policies tested with various availability scenarios
- Error handling tests: All exception paths covered

## Risk Mitigation

### Phase Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Policy conflict resolution unclear | Low | Medium | Document policy priority order clearly |
| Availability check slow for remote backends | Low | Low | No network calls in availability check |
| Cache staleness for availability status | Low | Low | Availability check is cheap, always re-check |
| Explicit AUTO backend type confusing | Medium | Medium | Clear error message explaining AUTO is for policy resolution only |

### Technical Considerations

1. **Availability Check Speed:**
   - Local (faster-whisper): Check if module installed + model downloaded
   - Cloud (OpenAI): Check if API key configured in config
   - No network calls in availability check

2. **Policy Resolution:**
   - AUTO: Prefer fastest available (CUDA > MPS > CPU for small files, else Cloud)
   - PREFER_LOCAL: Use faster-whisper if available, else OpenAI
   - PREFER_CLOUD: Use OpenAI if API key, else faster-whisper
   - Explicit backend: Bypass policy entirely

3. **Error Messages:**
   - Unavailable backend: BackendUnavailableError with backend name, reason, and suggestion
   - Invalid policy: ValueError with valid options
   - AUTO as explicit backend: ValueError explaining AUTO is for policy only

4. **Performance Considerations:**
   - Cache availability status per session (lazy evaluation)
   - Re-check on explicit request (reset cache)
   - No API calls in availability checks

## Implementation Notes

### Pattern Consistency

Follow existing patterns from BackendRegistry:
- Use singleton pattern only if needed for caching
- Thread-safe availability checks (if caching)
- Clear error messages with context and suggestions

### Policy Priority Order

```
AUTO policy:
  1. If CUDA available → faster-whisper (CUDA)
  2. If MPS available → faster-whisper (MPS)
  3. If OpenAI API key configured → OpenAI
  4. If CPU available → faster-whisper (CPU)
  5. Error: No backends available

PREFER_LOCAL policy:
  1. If faster-whisper available → faster-whisper
  2. If OpenAI API key configured → OpenAI
  3. Error: No backends available

PREFER_CLOUD policy:
  1. If OpenAI API key configured → OpenAI
  2. If faster-whisper available → faster-whisper
  3. Error: No backends available
```

### Integration Points

1. **TranscriptionOptions Integration:**
   - `backend` field (BackendType): explicit selection or AUTO
   - `backend_preference` field (SelectionPolicy): policy for auto-selection
   - Both fields have defaults (AUTO)

2. **BackendRegistry Integration:**
   - `BackendSelector` uses `BackendRegistry` to get backend instances
   - No direct import of backend implementations
   - Registry handles lazy loading

3. **Configuration Integration:**
   - OpenAI availability: check `AppConfig.openai.api_key` is set
   - Faster-whisper availability: check module import + model path
   - Cache check results per session

## Next Steps

After planning approval:
1. Execute Plan 08-01 (Backend Availability Checker)
2. Execute Plan 08-02 (Policy-Based Backend Selector)
3. Verify all success criteria met
4. Update STATE.md with completion notes