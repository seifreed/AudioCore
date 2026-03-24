---
phase: 01-foundation
plan: "02"
subsystem: types
tags: [enums, types, backend, format, error-classification, policy]

# Dependency graph
requires: []
provides:
  - BackendType enum for backend selection
  - ModelSize enum for model configuration
  - OutputFormat enum for output formatting
  - ModelErrorType enum for error classification
  - SelectionPolicy enum for automatic backend selection
  - Comprehensive error hierarchy (dependency)
affects: [backend-selection, transcription, error-handling]

# Tech tracking
tech-stack:
  added:
    - enum (Python standard library)
    - pytest (testing framework)
    - re (regex for camelCase parsing)
  patterns:
    - str, Enum inheritance for JSON serialization
    - parse() classmethod for case-insensitive parsing
    - Error code categorization (AUD-XXX by category)

key-files:
  created:
    - src/audiocore/__init__.py - Package initialization
    - src/audiocore/py.typed - Type hints marker file
    - src/audiocore/errors/__init__.py - Error hierarchy exports
    - src/audiocore/errors/base.py - Base exception classes
    - src/audiocore/errors/input.py - Input-related exceptions
    - src/audiocore/errors/config.py - Configuration exceptions
    - src/audiocore/errors/backend.py - Backend exceptions
    - src/audiocore/errors/api.py - API exceptions
    - src/audiocore/errors/processing.py - Processing exceptions
    - src/audiocore/types/__init__.py - Type definitions exports
    - src/audiocore/types/backend.py - BackendType and ModelSize enums
    - src/audiocore/types/format.py - OutputFormat enum
    - src/audiocore/types/error.py - ModelErrorType enum
    - src/audiocore/types/policy.py - SelectionPolicy enum
    - tests/unit/errors/*.py - Error hierarchy tests
    - tests/unit/types/*.py - Type enum tests
  modified: []

key-decisions:
  - "Inherit from str, Enum for JSON serialization support"
  - "Use parse() classmethod for case-insensitive string parsing"
  - "Number error codes by category (AUD-1xx input, AUD-2xx backend, etc.)"
  - "Provide default suggestions in error __init__ methods"
  - "Support extension detection in OutputFormat.parse()"

patterns-established:
  - "Enum with parse() classmethod pattern for CLI/config compatibility"
  - "Error hierarchy with error_code class attribute and context preservation"
  - "Comprehensive unit tests with >95% coverage requirement"

requirements-completed: [CORE-02]

# Metrics
duration: 7 min
completed: 2026-03-24
---

# Phase 1 Plan 02: Type Enums Summary

**Created typed enums for backend types, output formats, error classifications, and selection policies with CLI/config compatibility and comprehensive error hierarchy.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-24T16:40:38Z
- **Completed:** 2026-03-24T16:47:18Z
- **Tasks:** 3
- **Files modified:** 36 files created/modified

## Accomplishments

- Created 5 typed enums with JSON serialization and case-insensitive parsing
- Built comprehensive error hierarchy with 14 exception classes
- Implemented error code categorization (AUD-XXX by category)
- Added helper methods to ModelErrorType for error categorization
- Created 128 unit tests with 100% pass rate

## Task Commits

Each task was committed atomically:

1. **Task 1: Create BackendType and ModelSize enums** - `5c8a874` (feat)
2. **Task 2: Create SelectionPolicy, OutputFormat, and ModelErrorType enums** - `59d51b8` (feat)
3. **Task 3: Create unit tests for all enums** - `e5f36a8` (test)

**Plan metadata:** Will be committed with SUMMARY.md

## Files Created/Modified

### Type Definitions
- `src/audiocore/types/backend.py` - BackendType and ModelSize enums with parse() method
- `src/audiocore/types/format.py` - OutputFormat enum with extension detection
- `src/audiocore/types/error.py` - ModelErrorType enum with categorization methods
- `src/audiocore/types/policy.py` - SelectionPolicy enum with camelCase support

### Error Hierarchy
- `src/audiocore/errors/base.py` - AudioCoreError base class with error_code and context
- `src/audiocore/errors/input.py` - InputError, InvalidInputError, MediaFormatError
- `src/audiocore/errors/config.py` - ConfigurationError, InvalidConfigError
- `src/audiocore/errors/backend.py` - BackendError, BackendUnavailableError, TranscriptionError
- `src/audiocore/errors/api.py` - APIError, AuthenticationError, RateLimitError, APITimeoutError
- `src/audiocore/errors/processing.py` - ProcessingError, VADError

### Tests
- `tests/unit/types/test_backend.py` - 10 tests for BackendType/ModelSize
- `tests/unit/types/test_format.py` - 7 tests for OutputFormat
- `tests/unit/types/test_error.py` - 11 tests for ModelErrorType
- `tests/unit/types/test_policy.py` - 5 tests for SelectionPolicy
- `tests/unit/errors/test_base.py` - 13 tests for AudioCoreError
- `tests/unit/errors/test_input.py` - 19 tests for input exceptions
- `tests/unit/errors/test_config.py` - 10 tests for config exceptions
- `tests/unit/errors/test_backend.py` - 16 tests for backend exceptions
- `tests/unit/errors/test_api.py` - 22 tests for API exceptions
- `tests/unit/errors/test_processing.py` - 15 tests for processing exceptions

## Decisions Made

1. **str, Enum inheritance pattern** - Enables JSON serialization out of the box
2. **parse() classmethod** - Handles case-insensitive, hyphen/underscore, and camelCase inputs
3. **Error code categorization** - AUD-1xx (input), AUD-2xx (backend), AUD-3xx (API), AUD-4xx (processing)
4. **Default suggestions in __init__** - Provides helpful guidance by default
5. **Extension detection in OutputFormat** - Accepts both format name and file extension

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Created error hierarchy module**
- **Found during:** Task 1 execution
- **Issue:** Plan 01-02 imports from audiocore.errors but errors module didn't exist (depends on plan 01-01)
- **Fix:** Created complete error hierarchy with 14 exception classes as dependency
- **Files modified:** src/audiocore/errors/*.py, tests/unit/errors/*.py
- **Verification:** All imports resolve, all 128 tests pass
- **Committed in:** 5c8a874 (part of Task 1 commit)

**2. [Rule 3 - Blocking] Fixed parse() methods for camelCase/PascalCase**
- **Found during:** Task 3 verification (test failures)
- **Issue:** parse() methods didn't handle camelCase input like "PreferLocal"
- **Fix:** Added regex to insert underscore before uppercase letters, then lowercase
- **Files modified:** src/audiocore/types/policy.py, src/audiocore/types/error.py
- **Verification:** All parse tests pass (128/128)
- **Committed in:** e5f36a8 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both necessary for correctness and CLI compatibility. No scope creep.

## Issues Encountered

None - all tasks completed successfully with comprehensive tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Type definitions complete with JSON serialization and CLI/config compatibility
- Error hierarchy provides foundation for all error handling
- Ready for Phase 1 Plan 03 (domain models) or backend-specific implementations
- Tests establish pattern for future type definitions

## Self-Check

**Files verified:**
- `src/audiocore/types/backend.py` - FOUND
- `src/audiocore/types/format.py` - FOUND
- `src/audiocore/types/error.py` - FOUND
- `src/audiocore/types/policy.py` - FOUND
- All test files - FOUND

**Commits verified:**
- `5c8a874` - FOUND (feat(01-02): create BackendType and ModelSize enums)
- `59d51b8` - FOUND (feat(01-02): create SelectionPolicy, OutputFormat, and ModelErrorType enums)
- `e5f36a8` - FOUND (test(01-02): create unit tests for all enums and fix parse methods)
- `2ad6763` - FOUND (docs(01-02): complete type enums plan)

**Tests verified:**
- All 128 unit tests pass (100%)

## Self-Check: PASSED

---
*Phase: 01-foundation*
*Completed: 2026-03-24*