---
phase: 07-faster-whisper-backend
plan: 01
subsystem: backend
tags: [faster-whisper, huggingface-hub, gpu, cuda, mps, device-detection, model-manager, configuration]

# Dependency graph
requires:
  - phase: "05-backend-abstraction"
    provides: "Base TranscriptionBackend ABC, BackendRegistry pattern, error types"
  - phase: "01-foundation"
    provides: "AudioCoreError hierarchy, configuration patterns, ModelSize enum"
provides:
  - FasterWhisperConfig model with full validation
  - Device detection utilities (CUDA, MPS, CPU)
  - ModelManager for HuggingFace Hub model download and caching
  - Thread-safe singleton pattern for model management
affects: ["07-02", "07-03"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thread-safe singleton with class-level lock (ModelManager)"
    - "Lazy HuggingFace Hub import with graceful fallback"
    - "Pydantic validators with mode='before' for strict mode enum coercion"

key-files:
  created:
    - src/audiocore/config/faster_whisper_config.py
    - src/audiocore/backends/faster_whisper/__init__.py
    - src/audiocore/backends/faster_whisper/device.py
    - src/audiocore/backends/faster_whisper/model_manager.py
    - tests/unit/config/test_faster_whisper_config.py
    - tests/unit/backends/faster_whisper/__init__.py
    - tests/unit/backends/faster_whisper/test_device.py
    - tests/unit/backends/faster_whisper/test_model_manager.py

key-decisions:
  - "Use StrEnum for DeviceType and ComputeType for string serialization compatibility"
  - "Separate faster_whisper package under backends for future backend additions"
  - "Lazy HuggingFace Hub import in download_model() to avoid import errors when not installed"
  - "Thread-safe singleton pattern for ModelManager with explicit clear() method for testing"

patterns-established:
  - "Model validation with mode='before' for string-to-enum coercion in strict mode"
  - "Device detection with CUDA > MPS > CPU priority and graceful CPU fallback"
  - "Model caching in ~/.cache/huggingface/hub following HuggingFace conventions"

requirements-completed: [FAUX-02, FAUX-03]

# Metrics
duration: 15min
completed: "2026-03-25T10:47:00Z"
---

# Phase 07-01: Faster-Whisper Configuration and Model Manager Summary

**FasterWhisperConfig model with 15 validated fields, device detection utilities with CUDA/MPS/CPU auto-detection, and ModelManager singleton for HuggingFace Hub integration**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-25T10:31:48Z
- **Completed:** 2026-03-25T10:47:00Z
- **Tasks:** 4
- **Files modified:** 8

## Accomplishments

- FasterWhisperConfig Pydantic model with comprehensive validation for model size, device, compute type, and all decoding parameters
- Device detection utilities supporting CUDA, MPS (Apple Silicon), and CPU with automatic detection priority
- ModelManager singleton for thread-safe HuggingFace Hub model download and caching
- Complete test coverage (130 tests) with 74% code coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FasterWhisperConfig model** - `722a9ba` (feat)
2. **Task 2: Create device detection utilities** - `d10f51f` (feat)
3. **Task 3: Create ModelManager** - `3b23cdd` (feat)
4. **Task 4: Create faster_whisper package __init__.py** - `14ef90f` (feat)

## Files Created/Modified

- `src/audiocore/config/faster_whisper_config.py` - Configuration model with ComputeType enum, field validation
- `src/audiocore/backends/faster_whisper/__init__.py` - Package exports for all public API
- `src/audiocore/backends/faster_whisper/device.py` - GPU device detection with CUDA/MPS/CPU support
- `src/audiocore/backends/faster_whisper/model_manager.py` - HuggingFace Hub integration with thread-safe caching
- `src/audiocore/config/__init__.py` - Added FasterWhisperConfig to exports
- `tests/unit/config/test_faster_whisper_config.py` - 66 configuration tests
- `tests/unit/backends/faster_whisper/__init__.py` - Test package initialization
- `tests/unit/backends/faster_whisper/test_device.py` - 33 device detection tests
- `tests/unit/backends/faster_whisper/test_model_manager.py` - 31 model manager tests

## Decisions Made

1. **StrEnum for DeviceType and ComputeType** - String serialization compatible with faster-whisper API, inherits `str` for JSON compatibility
2. **Separate faster_whisper package under backends/** - Clean organization allowing future backend additions
3. **Lazy HuggingFace Hub import** - `from huggingface_hub import hf_hub_download` only in download_model() to avoid ImportError when not installed
4. **Thread-safe singleton with class-level Lock** - Same pattern as SileroVAD from Phase 04, reliable test mocking via clear() method
5. **Field validators with mode='before'** - Required for strict mode enum coercion from strings while maintaining type safety

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed beam_size validation test**
- **Found during:** Task 1 (FasterWhisperConfig tests)
- **Issue:** Tests set beam_size without matching best_of, triggering model validator error
- **Fix:** Added `best_of=10` and `best_of=20` in tests to satisfy `best_of >= beam_size` validation
- **Files modified:** tests/unit/config/test_faster_whisper_config.py
- **Verification:** All 66 config tests pass
- **Committed in:** `722a9ba` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed compute_type string validation in strict mode**
- **Found during:** Task 1 (FasterWhisperConfig validation)
- **Issue:** `strict=True` in Pydantic rejects string input for enum fields
- **Fix:** Added `@field_validator("compute_type", mode="before")` with `ComputeType.parse()` for string-to-enum coercion
- **Files modified:** src/audiocore/config/faster_whisper_config.py
- **Verification:** String inputs like `"int8"` correctly convert to `ComputeType.INT8`
- **Committed in:** `722a9ba` (Task 1 commit)

**3. [Rule 3 - Blocking] Fixed test mocking for internal import**
- **Found during:** Task 3 (ModelManager tests)
- **Issue:** `@patch` on `hf_hub_download` failed because import is inside function
- **Fix:** Used `patch.dict("sys.modules", {"huggingface_hub": mock_hf})` to mock the module import
- **Files modified:** tests/unit/backends/faster_whisper/test_model_manager.py
- **Verification:** All 31 model manager tests pass
- **Committed in:** `3b23cdd` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (3 bug fixes)
**Impact on plan:** All fixes ensure correctness - Pydantic strict mode works correctly, tests properly mock internal imports

## Issues Encountered

None - followed plan specifications closely. All deviations were implementation details handled automatically.

## User Setup Required

**External service: HuggingFace Hub**
- **Service:** HuggingFace Hub for model downloads
- **Why:** Optional dependency for faster-whisper model management
- **Setup:** No environment variables required - uses anonymous download by default
- **Verification:** `python -c "from audiocore.backends.faster_whisper import ModelManager; m = ModelManager(); print(m.list_models())"`

## Next Phase Readiness

- **Ready for Plan 07-02:** FasterWhisperBackend implementation using FasterWhisperConfig and ModelManager
- **FasterWhisperConfig:** Complete configuration model with all decoding parameters
- **ModelManager:** Thread-safe singleton ready for model loading in backend
- **Device detection:** Ready for automatic device selection in transcribe() calls
- **Test patterns:** Established patterns for mocking HuggingFace Hub imports

---

*Phase: 07-faster-whisper-backend*
*Completed: 2026-03-25*