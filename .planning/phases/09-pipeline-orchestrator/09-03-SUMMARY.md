---
phase: 09-pipeline-orchestrator
plan: 03
subsystem: output
tags: [formatting, json, text, serialization]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Segment, MediaInfo, TranscriptionOptions, TranscriptionResult models
  - phase: 02-configuration
    provides: AppConfig
provides:
  - Plain text output formatter with timestamps [HH:MM:SS.mmm]
  - JSON output formatter with full metadata serialization
  - formatted_output field in TranscriptionResult
  - Output formatting integration in Pipeline
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [pure functions for formatting, model_dump() for Pydantic serialization]

key-files:
  created:
    - src/audiocore/output/__init__.py
    - src/audiocore/output/text.py
    - src/audiocore/output/json.py
    - tests/unit/output/__init__.py
    - tests/unit/output/test_text.py
    - tests/unit/output/test_json.py
  modified:
    - src/audiocore/models/transcription.py (formatted_output field)
    - src/audiocore/pipeline/orchestrator.py (_format_result method)
    - tests/unit/pipeline/test_orchestrator.py (output formatting tests)

key-decisions:
  - "Pure functions for formatters (no side effects) for easy testing"
  - "formatted_output field in TranscriptionResult instead of separate output"
  - "Default to text format, use JSON when output_format is specified"
  - "UTF-8 encoding guaranteed with ensure_ascii=False in JSON"

patterns-established:
  - "Formatters are pure functions: format_text(result, options) -> str"
  - "JSON uses model_dump() for Pydantic serialization, then processes values"
  - "Enum types serialized to their string values"
  - "Float specials (inf, -inf, nan) serialized as None"

requirements-completed:
  - OUT-01  # Plain Text Output
  - OUT-02  # JSON Output

# Metrics
duration: 15 min
completed: 2026-03-25
---

# Phase 9 Plan 3: Plain Text and JSON Output Serializers Summary

**Output formatters for transcription results: plain text with timestamps and structured JSON with full metadata**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-25T12:23:57Z
- **Completed:** 2026-03-25T12:38:11Z
- **Tasks:** 4
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- Created output module with text and JSON formatters
- Implemented `format_text()` for timestamped plain text output `[HH:MM:SS.mmm] text`
- Implemented `format_json()` for structured JSON with full metadata
- Integrated formatters into Pipeline with `OutputFormat` selection
- Added `formatted_output` field to `TranscriptionResult`
- Achieved 100% test coverage on output module

## Task Commits

Each task was committed atomically:

1. **Task 1: Create output module and text formatter** - `0f78365` (feat)
2. **Task 2: Create JSON formatter** - `f2cdc05` (feat)
3. **Task 3: Integrate formatters into Pipeline** - `dedf858` (feat)
4. **Task 4: Write formatter unit tests** - `02c9f8c` (test)

## Files Created/Modified

- `src/audiocore/output/__init__.py` - Module entry point with exports
- `src/audiocore/output/text.py` - Plain text formatter with timestamps
- `src/audiocore/output/json.py` - JSON formatter with metadata
- `src/audiocore/models/transcription.py` - Added formatted_output field
- `src/audiocore/pipeline/orchestrator.py` - Added _format_result() and integration
- `tests/unit/output/test_text.py` - 19 text formatter tests
- `tests/unit/output/test_json.py` - 23 JSON formatter tests
- `tests/unit/pipeline/test_orchestrator.py` - 3 output formatting tests

## Decisions Made

- **Pure functions for formatters:** Formatters have no side effects, making them easy to test and reason about
- **formatted_output field in TranscriptionResult:** Result contains both raw segments and formatted output, avoiding separate output pipelines
- **Default text format:** Most common use case, JSON requires explicit `output_format=OutputFormat.JSON`
- **UTF-8 with ensure_ascii=False:** Preserves unicode characters correctly in JSON output

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tests pass, 100% coverage achieved.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

All key files verified:
- src/audiocore/output/__init__.py ✓
- src/audiocore/output/text.py ✓
- src/audiocore/output/json.py ✓
- tests/unit/output/test_text.py ✓
- tests/unit/output/test_json.py ✓

All commits verified:
- 0f78365 feat(09-03): create output module and text formatter
- f2cdc05 feat(09-03): create JSON formatter
- dedf858 feat(09-03): integrate formatters into Pipeline
- 02c9f8c test(09-03): add JSON formatter NaN/inf tests and clean up dead code
- acc1eb0 docs(09-03): complete output formatters plan

Test results: 44 tests pass, 100% coverage on output module