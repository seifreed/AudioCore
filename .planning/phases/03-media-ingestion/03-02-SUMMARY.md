---
phase: "03-media-ingestion"
plan: "02"
subsystem: media
tags: [ffmpeg, audio-extraction, wav, subprocess, progress-callback]

requires:
  - phase: "03-media-ingestion"
    plan: "01"
    provides: probe() function for duration detection, MediaError exception
provides:
  - extract_audio() function for media-to-WAV conversion
  - temp_audio_file context manager for automatic cleanup
  - Progress callback support during extraction
affects:
  - Phase 4 (VAD): Uses extract_audio for preprocessing
  - Phase 6 (Cloud Backend): Uses extract_audio for file preparation
  - Phase 7 (Local Backend): Uses extract_audio for file preparation

tech-stack:
  added: []
  patterns:
    - "ffmpeg subprocess for media conversion"
    - "Progress callback via stderr parsing"
    - "Context manager for temp file lifecycle"

key-files:
  created:
    - src/audiocore/media/extractor.py
    - tests/unit/media/test_extractor.py
  modified:
    - src/audiocore/media/__init__.py

key-decisions:
  - "16kHz mono PCM WAV as standard output format - optimal for speech recognition"
  - "Progress callback via stderr parsing for extraction progress tracking"
  - "NamedTemporaryFile with delete=False for temp file management"
  - "Fast seeking via -ss before -i in ffmpeg command"

patterns-established:
  - "Pattern: Command builder helpers for subprocess argument construction"
  - "Pattern: Output validation before returning (file exists, has content)"
  - "Pattern: Cleanup on error for temp files in exception handling"

requirements-completed: [MEDIA-02]

duration: 4 min
completed: "2026-03-24"
---

# Phase 3 Plan 02: Audio Extractor Summary

**extract_audio() function using ffmpeg subprocess for media-to-WAV conversion with progress callback support**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T21:47:15Z
- **Completed:** 2026-03-24T21:52:08Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- extract_audio() converts any media format to 16kHz mono WAV for transcription
- Supports start_time parameter for fast seeking (using -ss before -i)
- Supports duration parameter for limiting extraction length
- Creates temp file when output_path is None, returns Path to result
- Progress callback receives percentage updates during extraction (uses probe() for duration)
- temp_audio_file context manager for automatic cleanup of temporary files
- Comprehensive error handling: InvalidInputError for missing files, MediaError for ffmpeg failures

## Task Commits

Each task was committed atomically:

1. **Task 1 & 2: Implement extract_audio() and temp_audio_file context manager** - `158f72a` (feat)
2. **Task 3: Create unit tests for extract_audio function** - Included in same commit

**Note:** Tasks 1 and 2 implemented together since temp_audio_file is a supporting utility for extract_audio. Tests included in same atomic commit.

**Plan metadata:** (to be committed)

## Files Created/Modified

- `src/audiocore/media/extractor.py` - extract_audio() and temp_audio_file implementation
- `src/audiocore/media/__init__.py` - Export extract_audio and temp_audio_file
- `tests/unit/media/test_extractor.py` - 32 comprehensive unit tests

## Decisions Made

- **16kHz mono PCM WAV:** Standard format for speech recognition, optimized for transcription accuracy
- **Fast seeking:** -ss placed before -i in ffmpeg command for instant seeking without decoding entire file
- **Progress callback pattern:** Uses probe() to get total duration, parses ffmpeg stderr for time= field, calculates percentage
- **Temp file handling:** NamedTemporaryFile with delete=False, explicit cleanup in context manager

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

[RULE 3 - Blocking] Missing dependency: probe.py from plan 03-01
- **Found during:** Task execution startup
- **Issue:** Plan 03-02 requires probe.py for progress callback support
- **Resolution:** Verified 03-01 was already complete (probe.py committed in 22da5ba)
- **Impact:** No delay - dependency already satisfied

## User Setup Required

None - no external service configuration required. ffmpeg assumed available on system PATH.

## Next Phase Readiness

- extract_audio() ready for audio preprocessing in pipeline
- Progress callback support enables user feedback during long extractions
- temp_audio_file context manager enables clean temporary file handling
- Ready for Plan 03-03: VAD Segmentation

---
*Phase: 03-media-ingestion*
*Completed: 2026-03-24*