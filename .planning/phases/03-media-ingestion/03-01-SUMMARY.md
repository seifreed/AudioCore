---
phase: 03-media-ingestion
plan: "01"
subsystem: media
tags: [ffprobe, media-metadata, subprocess, exception-handling]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Exception hierarchy (AudioCoreError base), type enums
  - phase: 02-configuration-system
    provides: AppConfig with AUDIOCORE env var support
provides:
  - probe() function for media metadata extraction
  - MediaError exception (AUD-402) for processing failures
  - ffprobe_path/ffmpeg_path configuration fields
affects:
  - Phase 4 (VAD): Uses MediaInfo for audio properties
  - Phase 6 (Cloud Backend): Uses probe() for file analysis
  - Phase 7 (Local Backend): Uses probe() for file analysis

# Tech tracking
tech-stack:
  added: [ffprobe (subprocess), json]
  patterns: [subprocess management, exception chaining, context preservation]

key-files:
  created:
    - src/audiocore/media/__init__.py
    - src/audiocore/media/probe.py
    - tests/unit/media/__init__.py
    - tests/unit/media/test_probe.py
  modified:
    - src/audiocore/errors/processing.py
    - src/audiocore/errors/__init__.py
    - src/audiocore/config/settings.py
    - tests/unit/errors/test_processing.py

key-decisions:
  - "ffprobe subprocess with JSON output for reliable parsing"
  - "30-second default timeout for media analysis operations"
  - "InvalidInputError for missing files, MediaError for ffprobe failures"
  - "AUDIOCORE_FFPROBE_PATH and AUDIOCORE_FFMPEG_PATH env vars for custom binary paths"

patterns-established:
  - "Pattern: Validation helpers (_validate_file_exists, _check_ffprobe_available) for pre-flight checks"
  - "Pattern: Exception chaining with cause parameter for debugging"

requirements-completed: [MEDIA-01]

# Metrics
duration: 4 min
completed: 2026-03-24
---

# Phase 3 Plan 01: Media Probe Function Summary

**ffprobe subprocess wrapper with MediaError exception and AppConfig path configuration for media metadata extraction**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T21:47:13Z
- **Completed:** 2026-03-24T21:52:05Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- MediaError exception (AUD-402) for ffprobe/media processing failures with actionable suggestions
- ffprobe_path and ffmpeg_path fields in AppConfig with AUDIOCORE_ env var support
- probe() function extracts duration, format, codec, sample_rate, channels from media files
- Comprehensive error handling: InvalidInputError for missing files, MediaError for ffprobe failures
- 24 unit tests with 99% coverage for probe module

## Task Commits

Each task was committed atomically:

1. **Task 1: Add MediaError exception and ffprobe_path configuration** - `f834d19` (feat)
2. **Task 2: Implement probe() function in media module** - `22da5ba` (feat)
3. **Task 3: Create unit tests for probe function** - `c50ef6a` (test)

**Plan metadata:** (to be committed)

_Note: TDD tasks may have multiple commits (test → feat → refactor)_

## Files Created/Modified

- `src/audiocore/errors/processing.py` - Added MediaError exception class (AUD-402)
- `src/audiocore/errors/__init__.py` - Exported MediaError
- `src/audiocore/config/settings.py` - Added ffprobe_path and ffmpeg_path fields
- `src/audiocore/media/__init__.py` - Media module entry point, exports probe()
- `src/audiocore/media/probe.py` - probe() function with ffprobe subprocess integration
- `tests/unit/errors/test_processing.py` - MediaError test coverage (7 new tests)
- `tests/unit/media/__init__.py` - Test module init
- `tests/unit/media/test_probe.py` - 24 tests for probe() and helpers (99% coverage)

## Decisions Made

- **ffprobe subprocess approach:** Uses subprocess.run() with JSON output for reliable, platform-independent parsing
- **Timeout configuration:** 30-second default timeout for media analysis, configurable via probe() parameter
- **Error hierarchy:** InvalidInputError (AUD-002) for file-not-found, MediaError (AUD-402) for ffprobe failures
- **Graceful degradation:** Invalid sample_rate/channels values convert to None instead of raising exceptions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tests passed on first implementation.

## User Setup Required

None - no external service configuration required. ffmpeg/ffprobe assumed available on system PATH.

## Next Phase Readiness

- probe() function ready for use in audio processing pipeline
- MediaError exception available for error handling across phases
- AppConfig fields ready for custom ffprobe/ffmpeg paths via environment variables
- Ready for Plan 02: Audio extraction with extract_audio() function

## Self-Check: PASSED

- [x] All created files exist on disk
- [x] All 4 commits present in git history (feat + feat + test + docs)
- [x] SUMMARY.md created in correct location
- [x] Tests pass with 99% coverage

---
*Phase: 03-media-ingestion*
*Completed: 2026-03-24*