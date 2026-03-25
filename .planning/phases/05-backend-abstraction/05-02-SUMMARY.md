---
phase: 05-backend-abstraction
plan: 05-02
subsystem: backends
tags: [registry, singleton, thread-safe, lazy-loading, memoization]
requires: [05-01]
provides: [BackendRegistry]
affects: []
tech-stack:
  added:
    - BackendRegistry singleton class
    - Thread-safe lazy loading pattern
    - Backend instance memoization
  patterns:
    - Singleton pattern with double-checked locking
    - Class-level and instance-level locks for thread safety
    - Lazy instantiation on first access
    - Instance caching for performance
key-files:
  created:
    - src/audiocore/backends/registry.py
    - tests/unit/backends/test_registry.py
  modified:
    - src/audiocore/backends/__init__.py
decisions:
  - Class-level Lock for singleton initialization (same pattern as SileroVAD)
  - Instance-level Lock for backend instance creation (thread-safe memoization)
  - Lazy loading stores classes in _backends, instances created in _instances
  - BackendUnavailableError raised for unregistered backends with context dict
  - clear() method for test isolation with thread-safe locking
metrics:
  duration: 8 min
  completed_date: 2026-03-25
  tasks_completed: 4
  files_created: 2
  files_modified: 1
  test_coverage: 97%
  test_count: 27
---

# Phase 05 Plan 02: Backend Registry Summary

BackendRegistry singleton with thread-safe lazy loading and memoization for backend instance management.

## One-Liner

 Implemented thread-safe BackendRegistry singleton with lazy loading and memoization following the established SileroVAD pattern.

## Implementation

### Task 1: BackendRegistry Class
Created `src/audiocore/backends/registry.py` with:

**Thread-safe Singleton Pattern:**
- Class-level `_lock` for singleton initialization (double-checked locking)
- Instance-level `_instance_lock` for backend instance creation
- `_initialized` flag to prevent re-initialization

**Core Methods:**
- `__new__()` - Singleton with double-checked locking
- `__init__()` - Initialize _backends and _instances dicts
- `register()` - Register backend class, clear cached instance on re-register
- `get_backend()` - Lazy instantiate with memoization (thread-safe)
- `list_backends()` - Return list of registered BackendType values
- `is_available()` - Check registered + backend.is_available()
- `clear()` - Thread-safe clear for test isolation

**Key Design Decisions:**
1. **Lazy Loading:** Store classes in `_backends`, create instances on demand in `_instances`
2. **Memoization:** Cache instances for performance (same instance returned on subsequent calls)
3. **Thread Safety:** Two-level locking (class-level for singleton, instance-level for instances)
4. **Error Handling:** `BackendUnavailableError` with context dict for actionable debugging

### Task 2: Module Exports
Updated `src/audiocore/backends/__init__.py` to export `BackendRegistry`:
```python
from audiocore.backends.registry import BackendRegistry
__all__ = ["TranscriptionBackend", "is_backend_available", "BackendRegistry"]
```

### Task 3: Comprehensive Tests
Created `tests/unit/backends/test_registry.py` with 27 tests:

**Test Classes:**
- `TestSingletonPattern` - Same instance, thread-safe init, initialized once
- `TestRegister` - Add, overwrite, clear cache
- `TestGetBackend` - Instance retrieval, lazy loading, memoization, error handling
- `TestListBackends` - Registered types, empty state, state reflection
- `TestIsAvailable` - Available/unavailable/unregistered backends, exception handling
- `TestClear` - Remove backends/instances, thread-safety
- `TestThreadSafety` - Concurrent access, registration, state preservation
- `TestIntegration` - Full register→get→transcribe flow, multiple backends

**Coverage:** 97% (exceeds >95% target)

### Task 4: Integration Test
Integration tests included in test_registry.py:
- Full register → get_backend → transcribe flow verified
- Multiple backends accessed independently verified
- Registry state persists across singleton instances verified

## Deviations from Plan

None - plan executed exactly as written.

## Verification

### All Tests Pass
```bash
pytest tests/unit/backends/ -v
# 64 passed (37 from test_base.py + 27 from test_registry.py)
```

### Coverage Report
```bash
pytest tests/unit/backends/test_registry.py --cov=audiocore.backends.registry --cov-report=term-missing
# 97% coverage (52 statements, 0 missed, 2 partial branches)
```

### Import Verification
```python
from audiocore.backends import TranscriptionBackend, BackendRegistry, is_backend_available
from audiocore.types import BackendType

registry = BackendRegistry()
print(registry.list_backends())  # []
```

## Files Changed

| File | Action | Lines Changed | Description |
|------|--------|---------------|-------------|
| src/audiocore/backends/registry.py | Created | +197 | BackendRegistry singleton class |
| tests/unit/backends/test_registry.py | Created | +686 | 27 comprehensive unit tests |
| src/audiocore/backends/__init__.py | Modified | +2 | Export BackendRegistry |

## Architecture Alignment

### Pattern Consistency
- **Singleton Pattern:** Same double-checked locking approach as `SileroVAD` (Phase 4)
- **Thread Safety:** Class-level and instance-level locks
- **Error Handling:** `BackendUnavailableError` with context dict and suggestions
- **Type Hints:** Complete type hints using `TYPE_CHECKING` pattern

### Integration Points
- **Phase 1 Types:** Uses `BackendType` enum from `audiocore.types`
- **Phase 1 Errors:** Raises `BackendUnavailableError` from `audiocore.errors`
- **Phase 5 Base:** Returns `TranscriptionBackend` instances from `base.py`

## Next Steps

**Phase 6:** OpenAI Backend will:
```python
from audiocore.backends import BackendRegistry
from audiocore.types import BackendType

# Register on import
registry = BackendRegistry()
registry.register(BackendType.OPENAI, OpenAIBackend)

# Use anywhere
backend = registry.get_backend(BackendType.OPENAI)
result = backend.transcribe("audio.mp3", options)
```

**Phase 7:** Faster-Whisper Backend will:
```python
from audiocore.backends import BackendRegistry
from audiocore.types import BackendType

registry.register(BackendType.FASTER_WHISPER, FasterWhisperBackend)
```

## Self-Check: PASSED

✓ All files created exist
✓ All 3 commits exist in git log
✓ 27/27 tests pass
✓ Coverage = 97% (exceeds 95% target)
✓ Imports work correctly
✓ Thread-safety verified with concurrent tests