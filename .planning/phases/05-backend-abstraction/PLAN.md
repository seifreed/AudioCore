# Phase 5: Backend Abstraction

**Status:** Planning Complete  
**Goal:** Create extensible backend abstraction layer supporting multiple transcription engines  
**Depends on:** Phase 1 (Foundation) - COMPLETE  
**Requirements:** BACK-01, BACK-02

---

## Overview

This phase creates the architectural foundation for all transcription backends. It establishes a clean interface contract and a registry pattern that enables:

1. **New backends** - Easy addition of transcription engines by implementing TranscriptionBackend
2. **Backend discovery** - Runtime listing and availability checking
3. **Lazy loading** - Backends loaded on demand to avoid unnecessary dependencies
4. **Thread safety** - Concurrent access to registry from multiple threads

The abstraction layer isolates the core pipeline from implementation details, allowing OpenAI, faster-whisper, and future backends to be swapped without changes to calling code.

---

## Success Criteria (Goal-Backward Analysis)

**What must be TRUE for this phase to be complete:**

1. **Developer can create new backend** - By inheriting from TranscriptionBackend and implementing all abstract methods
2. **Backend registry lists available backends** - `list_backends()` returns all registered backends
3. **All backends implement transcribe()** - Consistent signature: `transcribe(path, options) -> TranscriptionResult`
4. **Backend availability check works** - `is_available()` returns True if backend is ready to use
5. **Registry retrieves by type** - `get_backend(BackendType.OPENAI)` returns correct backend instance
6. **Lazy loading prevents overhead** - Backend classes imported only when first accessed

---

## Must-Haves (Observable Truths)

### Truths
- Developer can create backend subclass implementing all abstract methods
- Registry returns backend instance by type
- Unavailable backends return False for is_available()
- List operation returns only registered backends
- Concurrent access doesn't corrupt registry state

### Artifacts
- `src/audiocore/backends/__init__.py` - Module entry point
- `src/audiocore/backends/base.py` - TranscriptionBackend ABC
- `src/audiocore/backends/registry.py` - BackendRegistry singleton
- `tests/unit/backends/test_base.py` - Interface tests
- `tests/unit/backends/test_registry.py` - Registry tests

### Key Links
- `TranscriptionBackend.transcribe()` uses `TranscriptionOptions` from Phase 1
- `TranscriptionBackend.transcribe()` returns `TranscriptionResult` from Phase 1
- `BackendRegistry.get_backend()` returns `TranscriptionBackend` instance
- Registry uses `BackendType` enum from Phase 1 for lookup

---

## Dependencies

### Internal Dependencies (Phase 1)
- `audiocore.types.BackendType` - Enum for backend identification
- `audiocore.errors.BackendError` - Exception base class
- `audiocore.errors.BackendUnavailableError` - Unavailable backend exception
- `audiocore.models.TranscriptionOptions` - Options model
- `audiocore.models.TranscriptionResult` - Result model
- `audiocore.models.MediaInfo` - Media metadata
- `audiocore.models.Segment` - Transcription segment

### Cross-Phase Dependencies
- **NONE** - This phase only depends on Phase 1 (Foundation)
- **Phases 6 & 7** (OpenAI, Faster-Whisper backends) will depend on this phase

---

## Plan Breakdown

### Plan 05-01: Backend Interface

**Objective:** Define TranscriptionBackend abstract base class establishing the contract all backends must implement

**Requirements:** BACK-01 (Backend Abstract Interface)

**Type:** Execute (autonomous)  
**Wave:** 1  
**Depends on:** []  
**Files Modified:**
- `src/audiocore/backends/__init__.py` (create)
- `src/audiocore/backends/base.py` (create)
- `tests/unit/backends/__init__.py` (create)
- `tests/unit/backends/test_base.py` (create)

**Must-Haves:**
- Truth: Developer can inherit from TranscriptionBackend and IDE shows abstract methods
- Truth: All abstract methods have complete type hints
- Truth: Cannot instantiate TranscriptionBackend directly
- Truth: Concrete subclass with missing methods fails to instantiate

**Tasks:**

#### Task 1: Create backend module structure
**Type:** auto  
**Files:**
- `src/audiocore/backends/__init__.py`
- `tests/unit/backends/__init__.py`

**Action:**
Create empty `__init__.py` files to establish the backend module structure. The `src/audiocore/backends/` directory will contain all backend-related code. Import TranscriptionBackend in the main `__init__.py` to expose it as `audiocore.backends.TranscriptionBackend`.

**Verification:**
```xml
<verify>
  <automated>python -c "from audiocore.backends import TranscriptionBackend; print('OK')" && echo "PASS"</automated>
</verify>
```

**Done:**
- Module imports successfully
- `from audiocore.backends import TranscriptionBackend` works

---

#### Task 2: Define TranscriptionBackend abstract base class
**Type:** auto  
**Files:**
- `src/audiocore/backends/base.py`

**Action:**
Create `TranscriptionBackend` ABC with the following abstract methods:
- `transcribe(audio_path: Path | str, options: TranscriptionOptions) -> TranscriptionResult` - Main transcription method
- `get_name() -> str` - Return human-readable backend name
- `is_available() -> bool` - Check if backend is ready to use (API key present, dependencies installed, etc.)
- `get_model_options() -> list[str]` - Return list of valid model names for this backend

Properties to define:
- `backend_type: BackendType` - Backend identifier enum

Implementation notes:
- Use `abc.ABC` and `@abstractmethod` decorator
- Add comprehensive docstrings to all methods
- All methods should raise `BackendUnavailableError` if called when `is_available()` returns False (except `is_available()` itself)
- Constructor should be optional (no required init params)
- Use existing error hierarchy patterns from Phase 1

Reference existing patterns:
- Error handling follows `AudioCoreError` pattern (error_code, context, suggestions)
- Type hints use `Path | str` for file parameters (established in Phase 3)
- Return types use Pydantic models from Phase 1

**Verification:**
```xml
<verify>
  <automated>pytest tests/unit/backends/test_base.py -v</automated>
</verify>
```

**Done:**
- TranscriptionBackend defined with all abstract methods
- ABC cannot be instantiated directly
- All methods have complete type hints
- Docstrings explain purpose and parameters

---

#### Task 3: Create comprehensive tests for TranscriptionBackend
**Type:** auto  
**Files:**
- `tests/unit/backends/test_base.py`

**Action:**
Create unit tests verifying:
1. **Concrete implementation works** - Create MinimalBackend subclass that implements all methods, verify it can be instantiated
2. **Abstract enforcement** - Attempting to instantiate TranscriptionBackend directly raises TypeError
3. **Missing method enforcement** - Subclass missing transcribe() fails to instantiate
4. **Type hints correct** - All method signatures match expected types
5. **Return types correct** - transcribe() returns TranscriptionResult (use mock implementation)
6. **is_available behavior** - Mock backend returns correct availability status

Test structure follows existing pattern from `tests/unit/types/test_backend.py` and `tests/unit/models/test_transcription.py`:
- One test class per feature area
- Descriptive test names explaining what's tested
- Arrange-Act-Assert structure
- Use pytest.raises for expected exceptions

Coverage target: >95% (following Phase 1-4 patterns)

**Verification:**
```xml
<verify>
  <automated>pytest tests/unit/backends/test_base.py --cov=audiocore.backends.base --cov-report=term-missing</automated>
</verify>
```

**Done:**
- 10+ test cases covering all abstract method behaviors
- Coverage >95% for base.py
- Tests pass with pytest

---

### Plan 05-02: Backend Registry

**Objective:** Implement BackendRegistry pattern for backend discovery and retrieval with lazy loading

**Requirements:** BACK-02 (Backend Registry)

**Type:** Execute (autonomous)  
**Wave:** 2  
**Depends on:** [05-01]  
**Files Modified:**
- `src/audiocore/backends/registry.py` (create)
- `src/audiocore/backends/__init__.py` (update to export registry)
- `tests/unit/backends/test_registry.py` (create)

**Must-Haves:**
- Truth: `list_backends()` returns all registered backend types
- Truth: `get_backend(BackendType.OPENAI)` returns backend instance
- Truth: Unavailable backends return False for `is_available()` but are still in registry
- Truth: Multiple threads can call registry concurrently without corruption
- Truth: Backend classes loaded only when first accessed

**Tasks:**

#### Task 1: Create BackendRegistry singleton
**Type:** auto  
**Files:**
- `src/audiocore/backends/registry.py`

**Action:**
Implement `BackendRegistry` class following the pattern from Phase 4 (SileroVAD thread-safe singleton):

```python
class BackendRegistry:
    """Registry for transcription backends with lazy loading and thread safety."""
    
    _instance: "BackendRegistry | None" = None
    _lock: threading.Lock = threading.Lock()  # Class-level lock for thread safety
    
    def __new__(cls) -> "BackendRegistry":
        """Singleton pattern with thread-safe initialization."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize registry with empty backend dict."""
        if self._initialized:
            return
        self._backends: dict[BackendType, type[TranscriptionBackend]] = {}
        self._instances: dict[BackendType, TranscriptionBackend] = {}
        self._initialized = True
```

Methods to implement:
- `register(backend_type: BackendType, backend_class: type[TranscriptionBackend]) -> None` - Register a backend class
- `get_backend(backend_type: BackendType) -> TranscriptionBackend` - Get backend instance (lazy instantiation)
- `list_backends() -> list[BackendType]` - List all registered backend types
- `is_available(backend_type: BackendType) -> bool` - Check if backend is available
- `clear() -> None` - Clear all registered backends (for testing)

Key implementation details:
- Store backend **classes** in `_backends` dict (lazy loading)
- Store backend **instances** in `_instances` dict (memoization)
- Create instance on first `get_backend()` call, not on registration
- Thread-safe instance creation using same lock pattern as SileroVAD
- Follow existing error patterns: raise `BackendUnavailableError` if backend not registered

**Verification:**
```xml
<verify>
  <automated>pytest tests/unit/backends/test_registry.py -v</automated>
</verify>
```

**Done:**
- Singleton pattern works (same instance from multiple calls)
- Lazy loading implemented (instances created on demand)
- Thread-safety with Lock class attribute

---

#### Task 2: Create MockBackend for testing
**Type:** auto  
**Files:**
- `tests/unit/backends/test_registry.py`

**Action:**
Create a `MockBackend` class implementing `TranscriptionBackend` for testing:
- Returns fake `TranscriptionResult` with minimal valid data
- `is_available()` configurable via constructor
- `get_name()` returns "Mock Backend"
- `get_model_options()` returns ["mock-model-1", "mock-model-2"]
- `backend_type = BackendType.OPENAI` (for testing)

This is a **test utility class**, not production code. It lives in the test file to avoid circular dependencies.

**Verification:**
```xml
<verify>
  <automated>python -c "from tests.unit.backends.test_registry import MockBackend; b = MockBackend(); print(b.get_name())"</automated>
</verify>
```

**Done:**
- MockBackend implements all abstract methods
- Can be instantiated for testing

---

#### Task 3: Create comprehensive registry tests
**Type:** auto  
**Files:**
- `tests/unit/backends/test_registry.py`

**Action:**
Create unit tests covering:

**Core Registry Behavior:**
1. **Singleton pattern** - Multiple `BackendRegistry()` calls return same instance
2. **Registration** - `register()` adds backend to registry
3. **Retrieval** - `get_backend()` returns backend instance
4. **Lazy loading** - Backend instance created only on first `get_backend()` call
5. **Instance caching** - Second `get_backend()` returns same instance (memoization)

**Availability Checks:**
6. **Available backend** - `is_available()` returns True for mock backend configured as available
7. **Unavailable backend** - `is_available()` returns False for unavailable backend
8. **Not registered** - `is_available()` returns False for unregistered backend type

**Listing Backends:**
9. **List registered** - `list_backends()` returns list of registered types
10. **Empty registry** - `list_backends()` returns empty list when no backends registered

**Error Handling:**
11. **Unregistered backend** - `get_backend()` raises `BackendUnavailableError` for unregistered type
12. **Error context** - Exception includes backend type in context dict

**Thread Safety:**
13. **Concurrent access** - Multiple threads calling `get_backend()` don't corrupt state
14. **Concurrent registration** - Multiple threads registering backends don't corrupt state

**Test Cleanup:**
15. **Clear registry** - `clear()` removes all backends for test isolation

Use `pytest.fixture` for test setup/teardown with registry clearing between tests.

**Verification:**
```xml
<verify>
  <automated>pytest tests/unit/backends/test_registry.py --cov=audiocore.backends.registry --cov-report=term-missing</automated>
</verify>
```

**Done:**
- 15+ test cases covering all registry behaviors
- Coverage >95% for registry.py
- Thread-safety verified
- Test isolation with clear() fixture

---

#### Task 4: Update module exports
**Type:** auto  
**Files:**
- `src/audiocore/backends/__init__.py`

**Action:**
Export public API from `__init__.py`:
```python
"""Transcription backend abstraction layer."""

from audiocore.backends.base import TranscriptionBackend
from audiocore.backends.registry import BackendRegistry

__all__ = ["TranscriptionBackend", "BackendRegistry"]
```

This allows users to import directly: `from audiocore.backends import TranscriptionBackend, BackendRegistry`

**Verification:**
```xml
<verify>
  <automated>python -c "from audiocore.backends import TranscriptionBackend, BackendRegistry; print('PASS')" && echo "OK"</automated>
</verify>
</verify>
```

**Done:**
- Public API exposed via `__init__.py`
- Imports work from top-level module

---

## Verification Plan

### Automated Tests
Each plan has automated verification via pytest:
- **Plan 05-01:** `pytest tests/unit/backends/test_base.py`
- **Plan 05-02:** `pytest tests/unit/backends/test_registry.py`

### Manual Verification (Post-Execution)
After completing both plans:

```bash
# Verify full test suite
pytest tests/unit/backends/ -v

# Verify coverage
pytest tests/unit/backends/ --cov=audiocore.backends --cov-report=html

# Verify imports work
python -c "
from audiocore.backends import TranscriptionBackend, BackendRegistry
from audiocore.types import BackendType
print(f'✓ TranscriptionBackend type: {TranscriptionBackend}')
print(f'✓ BackendRegistry type: {BackendRegistry}')
print(f'✓ BackendType has: {[b.value for b in BackendType]}')
"
```

### Integration Check
Create a temporary test script to verify end-to-end behavior:
```python
# test_backend_abstraction.py
from audiocore.backends import TranscriptionBackend, BackendRegistry
from audiocore.types import BackendType
from audiocore.models import TranscriptionOptions

# Create mock backend
class MockBackendImpl(TranscriptionBackend):
    @property
    def backend_type(self) -> BackendType:
        return BackendType.OPENAI
    
    def transcribe(self, audio_path, options):
        # Return fake result
        pass
    
    def get_name(self) -> str:
        return "Mock OpenAI"
    
    def is_available(self) -> bool:
        return True
    
    def get_model_options(self) -> list[str]:
        return ["gpt-4o-mini", "gpt-4o"]

# Register and retrieve
registry = BackendRegistry()
registry.register(BackendType.OPENAI, MockBackendImpl)

backend = registry.get_backend(BackendType.OPENAI)
assert backend.get_name() == "Mock OpenAI"
assert backend.is_available() == True
print("✓ Backend abstraction complete!")
```

---

## Success Criteria Checklist

After completing both plans, verify:

- [ ] `TranscriptionBackend` ABC defined with all abstract methods
- [ ] Cannot instantiate `TranscriptionBackend` directly (TypeError)
- [ ] Subclass must implement all abstract methods
- [ ] All methods have complete type hints
- [ ] `BackendRegistry` singleton works correctly
- [ ] Backends registered with `register(backend_type, backend_class)`
- [ ] Backends retrieved with `get_backend(backend_type)`
- [ ] Lazy loading: instances created on first access
- [ ] Thread-safe: concurrent access doesn't corrupt state
- [ ] `list_backends()` returns all registered types
- [ ] `is_available()` checks backend readiness
- [ ] Comprehensive unit tests (>95% coverage)
- [ ] Public API exposed via `audiocore.backends.__init__`

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Over-engineered interface | Keep interface minimal (YAGNI) - only methods needed for Phase 1 types |
| Thread safety issues | Use same Lock pattern as SileroVAD (Phase 4) - proven working |
| Lazy loading complexity | Clear separation: store classes in `_backends`, instances in `_instances` |
| Test coverage gaps | Follow existing test patterns from Phases 1-4 (>95% coverage) |
| Circular imports | Backend classes don't import registry; registry imports backend classes |

---

## Estimated Effort

| Plan | Complexity | Tasks | Estimated Duration |
|------|-----------|-------|-------------------|
| 05-01 | Low | 3 | 15-20 minutes |
| 05-02 | Low-Medium | 4 | 20-30 minutes |
| **Total** | | **7** | **35-50 minutes** |

**Context Budget:** ~35-45% per plan (well within 50% target for simple abstraction work)

---

## Next Phase Preview

**Phase 6: OpenAI Backend** will implement `OpenAIBackend` class:
- Inherit from `TranscriptionBackend`
- Implement all abstract methods
- Use OpenAI Whisper API
- Handle API errors with typed exceptions

**Phase 7: Faster-Whisper Backend** will implement `FasterWhisperBackend` class:
- Inherit from `TranscriptionBackend`
- Local model management
- GPU/CPU device handling

Both phases will register their backends with `BackendRegistry` at module load time.