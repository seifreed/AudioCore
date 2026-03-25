---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
last_updated: "2026-03-25T21:30:00Z"
progress:
  total_phases: 10
  completed_phases: 9
  total_plans: 26
  completed_plans: 26
---

# Project State

## Project Reference

See: .planning/PROJECT.md (created 2025-03-24)

**Core value:** AudioCore bridges cloud and local transcription with automatic backend selection, handling audio extraction, VAD segmentation, and output formatting so developers don't have to.

**Current focus:** Phase 10: Complete Interface - CLI, API, subtitle formats, and parallelism

## Current Position

Phase: 10 of 10 (Complete Interface)
Plan: 1 of 5 in current phase (in progress)
Status: Phase 10-01 complete (SRT and VTT formatters)
Last activity: 2026-03-25 — Plan 10-01 complete (SRT and VTT Output Serializers)

Progress: [█████████░] 90%

## Performance Metrics

**Velocity:**
- Total plans completed: 26
- Average duration: 12 min
- Total execution time: 5.2 hours

**By Phase:**

| Phase | Plans Completed | Total | Avg/Plan |
|-------|-----------------|-------|----------|
| 01-foundation | 3 | 3 | 6 min |
| 02-configuration-system | 3 | 3 | 28 min |
| 03-media-ingestion | 3 | 3 | 3 min |
| 04-vad-processing | 3 | 3 | 9 min |
| 05-backend-abstraction | 2 | 2 | 10 min |
| 06-openai-backend | 3 | 3 | 16 min |
| 07-faster-whisper-backend | 3 | 3 | 11 min |
| 08-backend-selection | 2 | 2 | 8 min |
| 09-pipeline-orchestrator | 4 | 4 | 15 min |
| 08-backend-selection | 2 | 2 | ? min |
| 09-pipeline-orchestrator | 3 | 4 | 11 min (so far) |

**Recent Trend:**
- 09-03: Text and JSON Output Formatters (15 min, 4 tasks, 8 files)
- 09-02: Progress Callbacks and Cancellation (11 min, 4 tasks, 6 files)
- 09-01: Pipeline Orchestrator Implementation (8 min, 4 tasks, 6 files)
- Trend: Output formatting with pure functions, JSON/Pydantic serialization
| Phase 09 P04 | 18 min | 4 tasks | 5 files |

## Accumulated Context

### Decisions

Project initialized with comprehensive roadmap based on specification.

Key architectural decisions:
- **Phase 1:** Pydantic v2 for all domain models and validation - provides strong typing and serialization out of the box
- **Phase 1:** Comprehensive exception hierarchy with error codes and context preservation - enables actionable error messages
- **Plan 01-01:** Error code categorization by category (AUD-001-099 input, AUD-100-199 config, etc.) — Enables programmatic error handling by code range
- **Plan 01-01:** Default suggestions per exception type, overridable by caller — Provides useful guidance while maintaining flexibility
- **Plan 01-02:** str, Enum inheritance for JSON serialization — Enables automatic JSON serialization without custom serializers
- **Plan 01-02:** parse() classmethod for case-insensitive CLI/config input — Handles various input formats: OpenAI, openai, OPENAI, prefer-local, PreferLocal
- **Plan 01-03:** strict=True and extra="forbid" on all models — Maximum type safety, rejects unknown fields
- **Plan 01-03:** model_validator for cross-field validation — validates Segment end_time >= start_time
- **Plan 02-01:** AUDIOCORE_ prefix for all environment variables — Clear namespacing, prevents conflicts
- **Plan 02-01:** SecretStr for API key storage — Prevents accidental logging/exposure of sensitive data
- **Plan 02-01:** field_validator for enum coercion — Case-insensitive env var parsing with helpful error messages
- **Plan 02-02:** Python 3.11+ tomllib for TOML parsing — No external dependency needed
- **Plan 02-02:** Flattened key extraction matching AppConfig fields — TOML section.key mapped to field names
- **Plan 02-03:** Priority chain: CLI > ENV > TOML > defaults — Configuration sources properly ordered
- **Plan 02-03:** model_size field alias — TOML/CLI use model_size, AppConfig uses model field with property for compatibility
- **Plan 03-01:** ffprobe subprocess with JSON output — Reliable parsing, platform-independent, subprocess timeout handling
- **Plan 03-01:** 30-second timeout default for probe — Reasonable for media files under 1GB, configurable via parameter
- **Plan 03-01:** InvalidInputError for missing files, MediaError for ffprobe failures — Clear error hierarchy for debugging
- **Plan 03-02:** 16kHz mono PCM WAV as standard output — Optimal format for speech recognition APIs
- **Plan 03-02:** Progress callback via stderr parsing — ffmpeg outputs time= field in stderr, parse for percentage
- **Plan 03-02:** NamedTemporaryFile with delete=False — Explicit control over temp file lifecycle for cleanup
- **Phase 3:** ffmpeg as subprocess rather than Python binding - simpler deployment, guaranteed compatibility
- **Phase 4:** Silero VAD via torch hub with cache fallback - automatic model management with offline capability
- **Plan 09-03:** Pure functions for output formatters — No side effects, easy to test, format_text() and format_json() return strings
- **Plan 09-03:** formatted_output field in TranscriptionResult — Result contains both raw segments and formatted output, avoiding separate output pipelines
- **Plan 09-02:** ProgressCallback as Protocol — Flexible interface for any callable, stage/progress/message signature
- **Plan 09-02:** PipelineStage as str, Enum — Automatic JSON serialization compatibility
- **Plan 09-02:** threading.Event for thread-safe cancellation — Atomic set/clear operations, wait() with timeout
- **Plan 09-02:** CancelledError AUD-500 — Pipeline category exception inheriting from AudioCoreError
- **Plan 09-02:** Cancellation checks at stage boundaries — Clean termination between PROBING, EXTRACTING, VAD, SELECTING, TRANSCRIBING, FORMATTING, COMPLETE
- **Plan 04-01:** Thread-safe Lock at class definition - reliable singleton pattern, enables test mocking
- **Plan 04-01:** VADConfig from audiocore.vad.config - reuse Pydantic validation, consistency with existing patterns
- **Plan 04-02:** env_nested_delimiter='__' for nested config - enables AUDIOCORE_VAD__* env vars
- **Plan 04-02:** Remove strict=True for nested models - allows pydantic-settings env var coercion
- **Plan 04-03:** Segment.text defaults to empty string - VAD creates segments before transcription fills text
- **Plan 04-03:** Merge confidence as minimum - conservative approach when combining short segments
- **Plan 04-03:** Equal-duration split algorithm - simple, effective for long segments
- **Phase 5:** Minimal backend interface - YAGNI principle, add capabilities as needed
- **Phase 5:** @property for backend_type instead of method - cleaner API, consistent with Python ABC patterns
- **Plan 05-02:** Class-level Lock for singleton initialization (same pattern as SileroVAD)
- **Plan 05-02:** Instance-level Lock for backend instance creation (thread-safe memoization)
- **Plan 05-02:** Lazy loading stores classes in _backends, instances created in _instances
- **Plan 05-02:** clear() method for test isolation with thread-safe locking
- **Phase 9:** Pipeline orchestrator owns cleanup - centralized temp file management via context managers
- [Phase 03-media-ingestion]: frozenset for format constants — immutable, performant, prevents accidental modification — Immutable constants are safer and thread-safe, membership testing is O(1)
- [Phase 03-media-ingestion]: Path | str type hints for format validation — accepts both string and Path objects — Flexible API that doesn't require callers to convert Path objects to strings
- [Phase 03-media-ingestion]: validate_format_or_raise() with MediaFormatError — provides actionable guidance for unsupported formats — Error messages include list of supported formats and suggestions for conversion
- **[Plan 06-01]:** Lazy client initialization - OpenAI client created on first transcribe() call to avoid unnecessary initialization
- **[Plan 06-01]:** API key format validation (sk- prefix) for early error detection before API calls
- **[Plan 06-01]:** Temperature mapping from model_size (tiny=0.0 to large=0.6) for deterministic output control
- **[Plan 06-01]:** All OpenAI exceptions mapped to AudioCore error hierarchy with context preservation and API key redaction
- **[Plan 06-02]:** Separate OpenAIConfig model for clean separation of concerns and future extensibility
- **[Plan 06-02]:** Priority chain for config resolution: OpenAIConfig.api_key > api_key parameter > OPENAI_API_KEY env var
- **[Plan 06-02]:** Optional organization and base_url fields for proxy/custom OpenAI endpoint support
- **[Plan 06-02]:** Default timeout 300s for large files, max_retries 2 for rate limit resilience
- **[Plan 06-03]:** Integration tests with pytest.mark.integration and graceful skip when no API key
- **[Plan 06-03]:** Explicit register_builtin_backends() function avoids import side effects
- **[Plan 06-03]:** Test audio file created dynamically with wave module (1-second silence)
 - **[Plan 06-03]:** Backend registry singleton with memization for single backend instance per type
 - **[Plan 07-01]:** StrEnum for DeviceType and ComputeType - string serialization compatible with faster-whisper API, inherits str for JSON compatibility
 - **[Plan 07-01]:** Separate faster_whisper package under backends/ - clean organization allowing future backend additions
 - **[Plan 07-01]:** Lazy HuggingFace Hub import in download_model() - avoids ImportError when huggingface-hub not installed
 - **[Plan 07-01]:** Thread-safe singleton pattern for ModelManager with class-level Lock - same pattern as SileroVAD, reliable test mocking via clear()
 - **[Plan 07-01]:** Field validators with mode='before' for Pydantic strict mode string-to-enum coercion - preserves strict=True while enabling string input
 - **[Plan 07-02]:** Lazy model loading in _load_model() method - model created on first transcribe() call to avoid startup overhead
 - **[Plan 07-02]:** Configuration parameters passed directly from FasterWhisperConfig to faster-whisper API - all config fields mapped to model.transcribe()
  - **[Plan 07-02]:** Minimum duration 0.01s fallback for zero-duration files - MediaInfo validation requirement
  - **[Plan 07-03]:** Integration tests skip gracefully when faster-whisper not installed - pytest.mark.skipif pattern
 - **[Plan 07-03]:** Test audio created dynamically with wave module (1-second silence) - no external fixtures needed
  - **[Plan 07-03]:** Pre-existing test failure (Segment.text empty string) documented as out of scope - deferred to Phase 4 cleanup
  - **[Plan 10-01]:** SRT and VTT subtitle formatters for video/web players
  - **[Plan 10-01]:** SRT uses comma (,) for milliseconds separator, VTT uses period (.) per specification

### Pending Todos

None yet.

### Blockers/Concerns

Phase considerations for upcoming work:
- **Phase 3:** ffmpeg must be available on system - document as prerequisite
- **Phase 4:** Silero VAD initial download requires internet connection - implement caching
- **Phase 6:** OpenAI API key required for integration tests (unit tests use mocks)

## Execution Notes

**Plan 01-01 Execution Order Deviation:**
The exception hierarchy work was completed and committed, but originally attributed to plan 01-02. This has been documented in 01-01-SUMMARY.md. All success criteria are met:
- ✓ All 14 exception classes defined with unique error codes
- ✓ All exceptions inherit from AudioCoreError
- ✓ Context dict preserved in all exceptions
- ✓ __cause__ preservation works
- ✓ 97 unit tests passing (>95% coverage)

**Plan 01-03 Issue:**
Initial tests for model_validate() failed because strict mode requires enum instances, not strings. Fixed by using enum instances directly in dict tests and string values for JSON tests (model_validate_json handles string→enum conversion automatically).

**Plan 02-03 Execution:**
Configuration priority chain implemented with merge_configs and load_config functions. Field alias mapping added for backward compatibility (model_size → model). All 98 config tests pass.

**Plan 03-01 Execution:**
Media probe function implemented with ffprobe subprocess. MediaError exception (AUD-402) added for processing failures. ffprobe_path and ffmpeg_path added to AppConfig. Validation helpers (_validate_file_exists, _check_ffprobe_available) provide pre-flight checks. All 24 unit tests pass with 99% coverage.

**Plan 03-02 Execution:**
Audio extractor function implemented with ffmpeg subprocess. extract_audio() converts any media format to 16kHz mono WAV for transcription. Progress callback support implemented via stderr time parsing with probe() for duration. temp_audio_file context manager added for clean temp file handling. All 32 unit tests pass.

**Plan 03-03 Execution:**
Format validation module with SUPPORTED_FORMATS constants for audio (mp3, wav, m4a, flac, ogg, aac) and video (mp4, mkv, avi, mov, webm). is_format_supported() provides case-insensitive extension validation. validate_format_or_raise() raises MediaFormatError with context dict containing supported_formats list and actionable suggestions. Comprehensive tests: 50 unit tests (>95% coverage), 16 integration tests (7 skip without ffmpeg/fixtures).

**Plan 04-01 Execution:**
Silero VAD integration with lazy model loading and thread-safe singleton caching. Implemented SileroVAD class with torch.hub primary loading and ~/.cache/torch fallback for offline operation. Audio loading handles stereo-to-mono conversion and sample rate validation (16kHz required). Speech detection processes audio in configurable chunk sizes (512 default). Used existing VADConfig from audiocore.vad.config instead of creating duplicate. Fixed lock initialization at class definition for reliable test mocking. 17 unit tests pass (1 skipped integration test).

**Plan 04-02 Execution:**
VADConfig Pydantic model created with 7 VAD parameters (min/max segment duration, speech/silence thresholds, speech pad, min silence duration, window size). Integrated into AppConfig with env_nested_delimiter='__' for AUDIOCORE_VAD__* env vars. Removed strict=True to enable pydantic-settings coercion. Cross-field validation ensures speech_threshold > silence_threshold and min_segment_duration < max_segment_duration. 32 unit tests pass with comprehensive coverage.

**Plan 04-03 Execution:**
Segment processing pipeline implemented with filter_by_confidence, merge_short_segments, split_long_segments, pad_segments, validate_segments, and to_segment_models functions. process_segments() orchestrates the full pipeline. detect_speech() convenience function integrates SileroVAD and segment processing. Fixed Segment model to allow empty text for VAD-created segments. 35 unit tests pass with comprehensive coverage. Two bug fixes applied: Segment.text default change and test assertion correction.

**Plan 05-02 Execution:**
BackendRegistry singleton with thread-safe lazy loading and memoization. Implemented two-level locking (class-level for singleton, instance-level for backend instances). Lazy loading stores classes in _backends dict, creates instances on demand in _instances dict. BackendUnavailableError raised for unregistered backends with context dict. Thread-safety verified with concurrent tests. 27 unit tests pass with 97% coverage. Two-level locking pattern matches SileroVAD approach from Phase 4.

**Plan 06-01 Execution:**
OpenAI backend implementation with comprehensive error handling and API key protection. Implemented lazy client initialization with API key validation (sk- prefix check). All 5 OpenAI exception types mapped to AudioCore error types with context preservation and suggestions. API key redaction in all error messages and logs. File handle cleanup via _safe_close_file() helper. Model size to temperature mapping for deterministic output. Minimum duration 0.01s for empty transcriptions. 32 unit tests pass with 93% coverage. Three auto-fixed blocking issues: UnboundLocalError for api_params, file handle cleanup, and OpenAI exception constructor signatures.

**Plan 06-02 Execution:**
OpenAI configuration model implemented with Pydantic SecretStr for secure API key storage. Created OpenAIConfig model with timeout (default 300s), max_retries (default 2), organization, and base_url fields. Field validation: timeout 1-3600s, max_retries 0-10. Integrated into AppConfig via default_factory pattern. Updated OpenAIBackend to accept config parameter with priority chain: config.api_key > api_key parameter > OPENAI_API_KEY env var. Config fields (organization, base_url, timeout) passed to OpenAI client initialization. Backward compatibility maintained with existing api_key parameter. 35 new tests pass with comprehensive coverage of SecretStr handling, priority chain, and integration.

**Plan 07-01 Execution:**
FasterWhisperConfig Pydantic model with 15 validated fields, device detection utilities with CUDA/MPS/CPU support, and ModelManager singleton for HuggingFace Hub integration. StrEnum for DeviceType and ComputeType for string serialization. Lazy HuggingFace Hub import in download_model() to avoid ImportError. Thread-safe singleton with class-level Lock (same pattern as SileroVAD). Field validators with mode='before' for strict mode enum coercion. 130 tests pass with 74% code coverage.

**Plan 07-03 Execution:**
Integration tests for FasterWhisperBackend with graceful skip pattern. Tests for BackendRegistry.register_builtin_backends() added. Test audio created with Python wave module (no external fixtures). Pre-existing test failure (Segment.text) documented as out of scope. 199 unit tests pass, 10 integration tests skip correctly when faster-whisper not installed. Coverage 74%.

**Plan 09-03 Execution:**
Output formatters for transcription results. Created output module with text.py and json.py formatters. format_text() produces timestamped output [HH:MM:SS.mmm] text. format_json() uses model_dump() for Pydantic serialization with enum handling. Added formatted_output field to TranscriptionResult. Integrated formatters into Pipeline with OutputFormat selection. 44 unit tests pass with 100% coverage on output module.

**Plan 09-04 Execution:**
Pipeline error recovery and cleanup implementation. Created pipeline-specific exception hierarchy (AUD-501 to AUD-504): PipelineError, PipelineStageError, PipelineCancelledError, PartialResultError. Each exception carries stage context and original_error. Refactored Pipeline.transcribe with stage-specific error wrapping, VAD fallback to whole-file transcription, and formatting error graceful handling. Added failed_segments field to TranscriptionResult for partial failure tracking. Comprehensive error recovery tests (23 tests, >95% coverage for error paths) covering cleanup, cancellation, VAD fallback, and user-friendly error messages. 102 pipeline tests passing.

**Plan 10-01 Execution:**
SRT and VTT subtitle formatters implemented. Created format_srt() and format_vtt() functions following existing text.py and json.py patterns. SRT uses comma (,) for milliseconds in HH:MM:SS,mmm format with sequential numbering starting from 1. VTT uses period (.) for milliseconds in HH:MM:SS.mmm format with WEBVTT header and no numbering. Both formatters handle empty segments gracefully (empty string for SRT, WEBVTT header only for VTT). 102 total output tests pass (text: 19, json: 23, srt: 24, vtt: 27, imports: 7). 100% coverage on output module.

## Session Continuity

Last session: 2026-03-25 (Phase 10-01 complete - SRT and VTT Output Serializers)
Stopped at: Plan 10-01 complete, Phase 10 in progress
Resume file: None

Next action: Continue Phase 10 with Plan 10-02 (CLI implementation)
  - **[Plan 09-01]:** Pipeline class with transcribe orchestration, uses BackendSelector for automatic backend selection, temp_file cleanup via context manager
  - **[Plan 09-02]:** Progress callbacks (ProgressCallback Protocol, PipelineStage enum), CancellationToken for clean termination
  - **[Plan 09-03]:** Output formatters (text/JSON), formatted_output in TranscriptionResult, pure functions for formatting
  - **[Plan 09-04]:** Pipeline exceptions (AUD-501 to AUD-504), VAD fallback, failed_segments field, error recovery tests
  - **[Plan 10-01]:** SRT and VTT formatters with proper timestamp formatting and subtitle format specifications