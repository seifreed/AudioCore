# REQUIREMENTS.md

## Requirement Categories

| Category | Code | Description |
|----------|------|-------------|
| Core Models | CORE | Domain types and validation |
| Configuration | CONF | Environment, files, defaults |
| Media Ingestion | MEDIA | Audio extraction and probing |
| VAD Processing | VAD | Voice activity detection |
| Backend Abstraction | BACK | Backend interface definition |
| OpenAI Backend | OPEN | Whisper API integration |
| Faster-Whisper Backend | FAUX | Local transcription |
| Backend Selection | SEL | Auto/explicit backend choice |
| Pipeline | PIPE | Orchestration and flow |
| Output | OUT | Serialization to formats |
| CLI | CLI | Command-line interface |
| API | API | Public library interface |
| Parallelism | PARA | Concurrent execution |
| Errors | ERR | Exception handling |

---

## v1 Requirements (MVP)

### CORE-01: Core Domain Models
**Priority:** P0 (Foundation)  
**Category:** Core Models

Define Pydantic models for all domain entities:
- `TranscriptionOptions`: Language, model size, backend preference
- `Segment`: Timestamps, text, confidence scores
- `TranscriptionResult`: Full result with metadata
- `MediaInfo`: Duration, format, codec info

**Acceptance:**
- All models use Pydantic v2 with strict validation
- All fields have type hints and docstrings
- Models serialize/deserialize correctly

### CORE-02: Type System
**Priority:** P0 (Foundation)  
**Category:** Core Models

Create typed enums and constants:
- `BackendType`: OPENAI, FASTER_WHISPER, AUTO
- `OutputFormat`: TEXT, JSON, SRT, VTT
- `ModelErrorType`: Classification of error types
- `SelectionPolicy`: PREFER_LOCAL, PREFER_CLOUD, AUTO

**Acceptance:**
- All enums have string values for CLI/config compatibility
- Type hints used throughout (no Any in public API)

### CONF-01: Environment Configuration
**Priority:** P0 (Foundation)  
**Category:** Configuration

Load configuration from environment variables:
- `AUDIOCORE_OPENAI_API_KEY`: OpenAI API key
- `AUDIOCORE_BACKEND`: Default backend selection
- `AUDIOCORE_MODEL`: Model size preference
- `AUDIOCORE_LANGUAGE`: Default language
- `AUDIOCORE_OUTPUT_FORMAT`: Default output format

**Acceptance:**
- All env vars follow AUDIOCORE_ prefix
- Missing optional vars use defaults
- API key never logged in plain text

### CONF-02: TOML Configuration File
**Priority:** P1 (Convenience)  
**Category:** Configuration

Support TOML configuration file at `~/.config/audiocore/config.toml`:
- Backend selection, model preferences
- Output format defaults
- Custom paths for models and cache
- Selection policy configuration

**Acceptance:**
- TOML file validated on load
- Invalid TOML raises typed exception
- Missing file uses defaults (not an error)

### CONF-03: Configuration Priority Chain
**Priority:** P0 (Foundation)  
**Category:** Configuration

Implement priority chain for configuration:
1. CLI arguments (highest)
2. Environment variables
3. TOML configuration file
4. Hardcoded defaults (lowest)

**Acceptance:**
- Priority order enforced correctly
- Merged configuration visible via API
- Priority conflicts logged at debug level

### MEDIA-01: Media Probing
**Priority:** P0 (Foundation)  
**Category:** Media Ingestion

Use ffprobe to extract media metadata:
- Duration, format, codec
- Sample rate, channels
- Bit rate, resolution (for video)

**Acceptance:**
- Probe completes in < 5 seconds for files < 1GB
- All standard formats supported (mp3, wav, mp4, mkv, etc.)
- Invalid files raise typed MediaError

### MEDIA-02: Audio Extraction
**Priority:** P0 (Foundation)  
**Category:** Media Ingestion

Extract and normalize audio via ffmpeg:
- Convert any format to 16kHz mono WAV
- Support seeking to start position
- Support duration limit
- Create temporary output file

**Acceptance:**
- Extraction preserves quality for transcription
- Progress callback supported
- Subprocess errors captured and re-raised

### MEDIA-03: Media Format Support
**Priority:** P0 (Foundation)  
**Category:** Media Ingestion

Support common media formats:
- Audio: mp3, wav, m4a, flac, ogg, aac
- Video: mp4, mkv, avi, mov, webm
- URL support for remote files (future consideration)

**Acceptance:**
- All listed formats can be probed and extracted
- Unsupported formats raise MediaFormatError with guidance

### VAD-01: Silero VAD Integration
**Priority:** P0 (Core)  
**Category:** VAD Processing

Integrate Silero VAD model for voice activity detection:
- Load model from Torch Hub or local cache
- Detect speech segments in audio
- Return timestamps with confidence scores

**Acceptance:**
- Model loaded on first use (lazy loading)
- VAD runs on CPU by default
- Memory usage reasonable for 1-hour audio (<2GB RAM)

### VAD-02: Segmentation Parameters
**Priority:** P1 (Quality)  
**Category:** VAD Processing

Configure VAD parameters:
- Min segment duration
- Max segment duration
- Silence threshold
- Padding around speech segments

**Acceptance:**
- Parameters configurable via config or API
- Defaults work well for most content
- Extreme values handled gracefully

### VAD-03: VAD Output Processing
**Priority:** P0 (Core)  
**Category:** VAD Processing

Convert VAD output to segment boundaries:
- Merge short segments
- Split long segments
- Maintain temporal order
- Generate segment timestamps

**Acceptance:**
- Segments maintain chronological order
- No overlapping segments
- Coverage of entire audio (no gaps > threshold)

### BACK-01: Backend Abstract Interface
**Priority:** P0 (Foundation)  
**Category:** Backend Abstraction

Define abstract backend interface:
- `transcribe(audio_path, options) -> TranscriptionResult`
- `get_name() -> str`
- `is_available() -> bool`
- `get_model_options() -> list[str]`

**Acceptance:**
- Interface defined with Python ABC
- All backends implement same interface
- Type hints complete

### BACK-02: Backend Registry
**Priority:** P0 (Foundation)  
**Category:** Backend Abstraction

Create backend registry pattern:
- Register available backends
- Get backend by type
- List all available backends

**Acceptance:**
- Backends registered at module load
- Registry query returns available backends only
- Registry thread-safe for concurrent access

### OPEN-01: OpenAI Whisper API Client
**Priority:** P0 (Core)  
**Category:** OpenAI Backend

Implement OpenAI Whisper API integration:
- Use official OpenAI SDK
- Send audio segments for transcription
- Handle API responses and errors

**Acceptance:**
- API key read securely from config
- Rate limits respected
- All API errors converted to typed exceptions

### OPEN-02: OpenAI Configuration
**Priority:** P1 (Quality)  
**Category:** OpenAI Backend

Support OpenAI-specific configuration:
- Model selection (whisper-1)
- Temperature setting
- Language hint
- Prompt hints for better accuracy

**Acceptance:**
- All OpenAI API parameters supported
- Configuration validated before API call
- Invalid parameters raise typed errors

### OPEN-03: OpenAI Error Handling
**Priority:** P0 (Foundation)  
**Category:** OpenAI Backend

Handle OpenAI API errors:
- Authentication errors
- Rate limit errors
- Server errors
- Network timeout errors

**Acceptance:**
- All error types mapped to exception hierarchy
- Error messages include actionable guidance
- API key redacted from all log output

### FAUX-01: Faster-Whisper Integration
**Priority:** P0 (Core)  
**Category:** Faster-Whisper Backend

Integrate faster-whisper CTranslate2 backend:
- Load model from HuggingFace or local cache
- Transcribe audio segments
- Return segments with timestamps

**Acceptance:**
- Model downloaded on first use
- GPU support automatic (CUDA/MPS)
- CPU fallback works reliably

### FAUX-02: Faster-Whisper Configuration
**Priority:** P1 (Quality)  
**Category:** Faster-Whisper Backend

Support faster-whisper configuration:
- Model size selection (tiny, base, small, medium, large)
- Device selection (cpu, cuda, auto)
- Beam size and other decoding options
- Language specification

**Acceptance:**
- All common parameters supported
- Invalid model names raise typed errors
- Device auto-detection works correctly

### FAUX-03: Faster-Whisper Model Management
**Priority:** P1 (Quality)  
**Category:** Faster-Whisper Backend

Model download and caching:
- Download from HuggingFace on demand
- Cache in user directory
- List available models
- Delete cached models

**Acceptance:**
- Download progress callback supported
- Cache location configurable
- Model size validation before download

### SEL-01: Automatic Backend Selection
**Priority:** P1 (Quality)  
**Category:** Backend Selection

Implement automatic backend selection:
- Selection policies: PREFER_LOCAL, PREFER_CLOUD, AUTO
- Consider availability, file size, cost preferences
- Make deterministic choice based on policy

**Acceptance:**
- AUTO selects fastest available backend
- PREFER_LOCAL falls back to cloud only if unavailable
- PREFER_CLOUD uses local only if API key missing

### SEL-02: Backend Availability Checks
**Priority:** P0 (Foundation)  
**Category:** Backend Selection

Check backend availability before use:
- OpenAI: API key present
- Faster-Whisper: Dependencies installed, model available
- Report which backends are available

**Acceptance:**
- Availability check fast (< 1 second for local backends)
- Check does not make network calls for local backends
- Availability status cached appropriately

### SEL-03: Explicit Backend Selection
**Priority:** P0 (Foundation)  
**Category:** Backend Selection

Allow explicit backend selection via CLI or API:
- CLI: `--backend openai` or `--backend faster-whisper`
- API: `backend=BackendType.OPENAI` parameter
- Raise error if selected backend unavailable

**Acceptance:**
- Explicit selection overrides all policy
- Clear error message if backend unavailable
- Backend name case-insensitive

### PIPE-01: Pipeline Orchestrator
**Priority:** P0 (Core)  
**Category:** Pipeline

Implement main transcription pipeline:
1. Validate input and configuration
2. Probe media file
3. Extract and normalize audio
4. Run VAD segmentation
5. Select backend (if AUTO)
6. Transcribe segments
7. Merge and post-process results
8. Format output

**Acceptance:**
- Pipeline completes for supported formats
- Each stage logs progress at appropriate level
- Failures at any stage raise typed exceptions

### PIPE-02: Progress Callbacks
**Priority:** P2 (UX)  
**Category:** Pipeline

Support progress callbacks for CLI and API:
- Stage change notifications
- Progress percentage within stage
- Estimated time remaining
- Cancellation support

**Acceptance:**
- Callbacks invoked at regular intervals
- CLI progress bar updates smoothly
- Cancellation stops processing cleanly

### PIPE-03: Pipeline Error Recovery
**Priority:** P1 (Reliability)  
**Category:** Pipeline

Handle errors gracefully at each stage:
- Temp files cleaned up on failure
- Partial results preserved when possible
- User-friendly error messages

**Acceptance:**
- Cleanup guaranteed via context managers
- Partial transcriptions available via API
- Error context included in exception

### OUT-01: Plain Text Output
**Priority:** P0 (Core)  
**Category:** Output

Plain text output format:
- Simple text with timestamps per line
- `speaker` format: `[00:00:00] speaker: text`
- Speaker field optional (not in v1.0 scope)

**Acceptance:**
- Text readable and parseable
- Timestamps in HH:MM:SS.mmm format
- UTF-8 encoding always used

### OUT-02: JSON Output
**Priority:** P0 (Core)  
**Category:** Output

Structured JSON output:
- Full transcription result with metadata
- Segments array with all fields
- Configuration used
- Timing and backend info

**Acceptance:**
- JSON valid and parseable
- Schema documented
- Minification optional via config

### OUT-03: SRT Subtitle Format
**Priority:** P1 (Common)  
**Category:** Output

SRT subtitle format:
- Standard subtitle format
- Sequential numbering
- Timestamps in SRT format
- Text content for each segment

**Acceptance:**
- Output valid SRT format
- Compatible with video players
- Line length wrapping handled

### OUT-04: VTT WebVTT Format
**Priority:** P1 (Common)  
**Category:** Output

WebVTT subtitle format:
- Header with WEBVTT identifier
- Cue timings in VTT format
- Optional styling cues (future)

**Acceptance:**
- Output valid VTT format
- Compatible with web players
- Speaker cues optional (not in v1.0 scope)

### OUT-05: Output File Writing
**Priority:** P1 (Convenience)  
**Category:** Output

Write output to file or stdout:
- Directory creation if needed
- Filename from input or explicit
- Overwrite protection option

**Acceptance:**
- Files written atomically (temp then move)
- Permissions set correctly
- Stdout works without file system

### CLI-01: Transcribe Command
**Priority:** P0 (Core)  
**Category:** CLI

Main CLI transcribe command:
- `audiocore transcribe <input_file>`
- Accept all configuration as flags
- Auto-detect output format from extension
- Progress display

**Acceptance:**
- Command intuitive and documented
- Help text comprehensive (--help)
- Exit codes meaningful (0 success, non-zero error)

### CLI-02: Backend Commands
**Priority:** P1 (Convenience)  
**Category:** CLI

Backend management commands:
- `audiocore backends list`: Show available backends
- `audiocore backends check`: Validate backend setup

**Acceptance:**
- Commands work without API keys (list)
- Check command validates configuration

### CLI-03: Model Management Commands
**Priority:** P2 (Maintenance)  
**Category:** CLI

Model management (faster-whisper):
- `audiocore models list`: List downloaded models
- `audiocore models download <model>`: Download model
- `audiocore models remove <model>`: Delete model

**Acceptance:**
- Commands work offline for list
- Download shows progress
- Remove confirms before deletion

### CLI-04: Configuration Display
**Priority:** P2 (UX)  
**Category:** CLI

Configuration display command:
- `audiocore config show`: Show current configuration
- `audiocore config path`: Show config file location

**Acceptance:**
- API keys redacted in output
- Show source of each value (env, file, default)

### API-01: Public Transcription API
**Priority:** P0 (Core)  
**Category:** API

Python library API for transcription:
- `transcribe(path, options=None) -> TranscriptionResult`
- Options object with all configurables
- Returns result object with all metadata

**Acceptance:**
- API documented with docstrings
- Type hints complete and correct
- Works without CLI installed

### API-02: API Error Handling
**Priority:** P0 (Foundation)  
**Category:** API

Typed exception hierarchy for all errors:
- `AudioCoreError`: Base exception
- `ConfigurationError`: Config problems
- `MediaError`: Media processing problems
- `BackendError`: Backend problems
- `TranscriptionError`: Transcription failures

**Acceptance:**
- All public errors inherit from AudioCoreError
- Error messages actionable and clear
- Original exceptions wrapped with context

### API-03: Async API Support
**Priority:** P2 (Enhancement)  
**Category:** API

Async version of transcription API:
- `async_transcribe(path, options) -> TranscriptionResult`
- Non-blocking for concurrent use
- Compatible with asyncio event loops

**Acceptance:**
- Async API mirrors sync API
- Concurrent transcriptions work correctly
- Cancellation handled properly

### PARA-01: Parallel Segment Processing
**Priority:** P1 (Performance)  
**Category:** Parallelism

Process segments in parallel for speed:
- VAD segments can be processed concurrently
- OpenAI API allows concurrent requests
- Faster-whisper works on segments in parallel

**Acceptance:**
- Parallel processing optional (config flag)
- Results maintain temporal order
- Performance improvement measurable

### PARA-02: Concurrent File Processing
**Priority:** P2 (Batch)  
**Category:** Parallelism

Process multiple files concurrently:
- CLI `--parallel N` option
- API supports file list input
- Progress aggregation

**Acceptance:**
- Concurrent file processing works
- Memory usage bounded
- Individual file failures don't stop others

### ERR-01: Exception Hierarchy
**Priority:** P0 (Foundation)  
**Category:** Errors

Create comprehensive exception hierarchy:
- Base: `AudioCoreError`
- Input: `InvalidInputError`, `MediaFormatError`
- Config: `ConfigurationError`, `InvalidConfigError`
- Backend: `BackendError`, `BackendUnavailableError`
- API: `AuthenticationError`, `RateLimitError`, `APIError`
- Processing: `TranscriptionError`, `VADError`

**Acceptance:**
- All exceptions have error codes
- Messages include remediation hints
- String representation user-friendly

### ERR-02: Error Context Preservation
**Priority:** P1 (Quality)  
**Category:** Errors

Preserve error context in exceptions:
- Wrap underlying exceptions with context
- Include file path, operation being performed
- Include suggestions for resolution

**Acceptance:**
- All exceptions carry context dict
- Original exception preserved
- Debug-level logs contain full stack traces

### ERR-03: Graceful Degradation
**Priority:** P1 (Reliability)  
**Category:** Errors

Handle partial failures gracefully:
- VAD failures can fall back to whole-file processing
- Single segment failures don't fail entire transcription
- Warnings logged for partial issues

**Acceptance:**
- Partial results available via API
- CLI shows warnings for issues
- Clear indication of partial vs complete

---

## v2 Requirements (Future)

### CORE-03: Speaker Diarization Support
**Priority:** Future  
**Category:** Core Models  
Add speaker identification to segments.

### MEDIA-04: Remote Media URLs
**Priority:** Future  
**Category:** Media Ingestion  
Download and process remote media files.

### OUT-06: Speaker Labeling Output
**Priority:** Future  
**Category:** Output  
Include speaker labels in all output formats.

### API-04: Streaming Transcription
**Priority:** Future  
**Category:** API  
Real-time transcription API.

---

## Requirement Counts

| Category | v1 Count | v2 Count |
|----------|----------|----------|
| CORE | 2 | 1 |
| CONF | 3 | 0 |
| MEDIA | 3 | 1 |
| VAD | 3 | 0 |
| BACK | 2 | 0 |
| OPEN | 3 | 0 |
| FAUX | 3 | 0 |
| SEL | 3 | 0 |
| PIPE | 3 | 0 |
| OUT | 5 | 1 |
| CLI | 4 | 0 |
| API | 3 | 1 |
| PARA | 2 | 0 |
| ERR | 3 | 0 |
| **Total** | **39** | **4** |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1: Foundation | Complete |
| CORE-02 | Phase 1: Foundation | Complete |
| ERR-01 | Phase 1: Foundation | Complete |
| ERR-02 | Phase 1: Foundation | Complete |
| CONF-01 | Phase 2: Configuration System | Pending |
| CONF-02 | Phase 2: Configuration System | Complete |
| CONF-03 | Phase 2: Configuration System | Pending |
| MEDIA-01 | Phase 3: Media Ingestion | Pending |
| MEDIA-02 | Phase 3: Media Ingestion | Pending |
| MEDIA-03 | Phase 3: Media Ingestion | Pending |
| VAD-01 | Phase 4: VAD Processing | Pending |
| VAD-02 | Phase 4: VAD Processing | Pending |
| VAD-03 | Phase 4: VAD Processing | Pending |
| BACK-01 | Phase 5: Backend Abstraction | Pending |
| BACK-02 | Phase 5: Backend Abstraction | Pending |
| OPEN-01 | Phase 6: OpenAI Backend | Pending |
| OPEN-02 | Phase 6: OpenAI Backend | Pending |
| OPEN-03 | Phase 6: OpenAI Backend | Pending |
| FAUX-01 | Phase 7: Faster-Whisper Backend | Pending |
| FAUX-02 | Phase 7: Faster-Whisper Backend | Pending |
| FAUX-03 | Phase 7: Faster-Whisper Backend | Pending |
| SEL-01 | Phase 8: Backend Selection | Pending |
| SEL-02 | Phase 8: Backend Selection | Pending |
| SEL-03 | Phase 8: Backend Selection | Pending |
| PIPE-01 | Phase 9: Pipeline & Core Output | Pending |
| PIPE-02 | Phase 9: Pipeline & Core Output | Pending |
| PIPE-03 | Phase 9: Pipeline & Core Output | Pending |
| OUT-01 | Phase 9: Pipeline & Core Output | Pending |
| OUT-02 | Phase 9: Pipeline & Core Output | Pending |
| ERR-03 | Phase 9: Pipeline & Core Output | Pending |
| OUT-03 | Phase 10: Complete Interface | Pending |
| OUT-04 | Phase 10: Complete Interface | Pending |
| OUT-05 | Phase 10: Complete Interface | Pending |
| CLI-01 | Phase 10: Complete Interface | Pending |
| CLI-02 | Phase 10: Complete Interface | Pending |
| CLI-03 | Phase 10: Complete Interface | Pending |
| CLI-04 | Phase 10: Complete Interface | Pending |
| API-01 | Phase 10: Complete Interface | Pending |
| API-02 | Phase 10: Complete Interface | Pending |
| API-03 | Phase 10: Complete Interface | Pending |
| PARA-01 | Phase 10: Complete Interface | Pending |
| PARA-02 | Phase 10: Complete Interface | Pending |

**Coverage Summary:** 39/39 v1 requirements mapped to phases