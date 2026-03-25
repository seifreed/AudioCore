---
phase: 09-pipeline-orchestrator
type: phase-plan
created: 2026-03-25
status: planning
requirements:
  - PIPE-01  # Pipeline Orchestrator
  - PIPE-02  # Progress Callbacks
  - PIPE-03  # Pipeline Error Recovery
  - OUT-01   # Plain Text Output
  - OUT-02   # JSON Output
  - ERR-03   # Graceful Degradation
---

# Phase 9: Pipeline Orchestrator

## Phase Goal

Implement the main transcription pipeline that orchestrates end-to-end workflow from media input to formatted output, with progress notifications, error recovery, and clean resource management.

**Purpose:** Connect all infrastructure components (media ingestion, VAD, backends, selection) into a cohesive pipeline that users can run as `transcribe(path)` with automatic cleanup on failure.

**Output:** Pipeline class with stage-based orchestration, progress callbacks, cancellation support, output formatting (text/JSON), and guaranteed cleanup via context managers.

## Dependencies

### Cross-Phase Dependencies

```
Phase 1 (Foundation) ──► Phase 9
  - AudioCoreError hierarchy (AudioCoreError, MediaError, TranscriptionError, VADError, BackendError)
  - Segment, MediaInfo, TranscriptionOptions, TranscriptionResult models
  - BackendType, OutputFormat enums

Phase 2 (Configuration) ──► Phase 9
  - AppConfig with all configuration merged
  - OpenAIConfig, FasterWhisperConfig, VADConfig

Phase 3 (Media Ingestion) ──► Phase 9
  - probe(path) ──> MediaInfo
  - extract_audio(input, output, progress_callback) ──> Path
  - temp_audio_file context manager for cleanup
  - SUPPORTED_FORMATS, is_format_supported, validate_format_or_raise

Phase 4 (VAD Processing) ──► Phase 9
  - detect_speech(audio_path, config, duration) ──> list[Segment]
  - VADConfig with speech thresholds, segment duration limits
  - process_segments() for merge/split/pad operations

Phase 5 (Backend Abstraction) ──► Phase 9
  - TranscriptionBackend ABC (backend_type, transcribe, is_available, get_name)
  - BackendRegistry (register, get_backend, is_available, list_backends)

Phase 6 (OpenAI Backend) ──► Phase 9
  - OpenAIBackend implementation
  - OpenAIConfig with api_key (SecretStr)

Phase 7 (Faster-Whisper Backend) ──► Phase 9
  - FasterWhisperBackend implementation
  - FasterWhisperConfig with model/device settings
  - ModelManager for model availability

Phase 8 (Backend Selection) ──► Phase 9
  - BackendSelector.select(backend, policy) ──> BackendType
  - BackendAvailabilityChecker for pre-flight checks
  - SelectionPolicy for policy-based selection
```

### Internal File Dependencies

```
audiocore/media/__init__.py ──► probe, extract_audio, temp_audio_file, validate_format_or_raise
audiocore/vad/__init__.py ──► detect_speech, VADConfig
audiocore/backends/__init__.py ──► TranscriptionBackend, BackendRegistry, BackendSelector
audiocore/models/__init__.py ──► Segment, MediaInfo, TranscriptionOptions, TranscriptionResult
audiocore/config/__init__.py ──► AppConfig, load_config
audiocore/types/__init__.py ──► BackendType, OutputFormat, SelectionPolicy
audiocore/errors/__init__.py ──► AudioCoreError hierarchy
```

## Goal-Backward Analysis

### Goal Statement

User can call `transcribe(path, options)` and the system automatically probes media, extracts audio, runs VAD, selects backend, transcribes segments, merges results, and returns formatted output — with progress notifications, clean cancellation, and guaranteed temp file cleanup on failure.

### Observable Truths (What must be TRUE for goal achievement)

1. **Pipeline Execution:** User can run `transcribe(path)` and get TranscriptionResult without managing any intermediate steps
2. **Progress Notifications:** Progress callback receives stage change events and percentage updates during long operations
3. **Cancellation:** User can cancel mid-pipeline and all temp files are cleaned up
4. **Error Recovery:** Pipeline failures clean up temp files and provide partial results via API
5. **Plain Text Output:** User can get transcription as timestamped text format `[HH:MM:SS.mmm] text`
6. **JSON Output:** User can get full transcription result as structured JSON with metadata
7. **Backend Auto-Selection:** AUTO backend type works correctly through BackendSelector
8. **Format Validation:** Unsupported media formats raise MediaFormatError before processing starts

### Required Artifacts

| Artifact | Purpose | Min Lines | Key Exports |
|----------|---------|-----------|-------------|
| `src/audiocore/pipeline/__init__.py` | Pipeline module entry point | 30 | `Pipeline`, `transcribe`, `ProgressCallback` |
| `src/audiocore/pipeline/orchestrator.py` | Pipeline orchestration logic | 350 | `Pipeline` class |
| `src/audiocore/pipeline/progress.py` | Progress callbacks and events | 80 | `ProgressCallback`, `PipelineStage`, `ProgressEvent` |
| `src/audiocore/pipeline/cancellation.py` | Cancellation token and support | 60 | `CancellationToken`, `CancelledError` |
| `src/audiocore/output/__init__.py` | Output formatters module | 25 | `format_text`, `format_json` |
| `src/audiocore/output/text.py` | Plain text formatter | 60 | `format_text` |
| `src/audiocore/output/json.py` | JSON formatter | 50 | `format_json` |
| `tests/unit/pipeline/test_orchestrator.py` | Pipeline unit tests | 450 | Test classes |
| `tests/unit/pipeline/test_progress.py` | Progress callback tests | 150 | Test classes |
| `tests/unit/output/test_text.py` | Text formatter tests | 150 | Test classes |
| `tests/unit/output/test_json.py` | JSON formatter tests | 100 | Test classes |

### Required Wiring

```yaml
key_links:
  - from: "Pipeline.transcribe()"
    to: "validate_format_or_raise"
    via: "media ingestion"
    pattern: "validate_format_or_raise(path) → raise MediaFormatError if unsupported"
    
  - from: "Pipeline.transcribe()"
    to: "probe"
    via: "media probing"
    pattern: "probe(path) → MediaInfo(duration, format, codec)"
    
  - from: "Pipeline.transcribe()"
    to: "extract_audio"
    via: "audio extraction"
    pattern: "extract_audio(path, temp_path, progress_callback) → Path to 16kHz WAV"
    
  - from: "Pipeline.transcribe()"
    to: "detect_speech"
    via: "VAD processing"
    pattern: "detect_speech(audio_path, vad_config, duration) → list[Segment]"
    
  - from: "Pipeline.transcribe()"
    to: "BackendSelector.select"
    via: "backend selection"
    pattern: "select_backend(options.backend, options.backend_preference) → BackendType"
    
  - from: "Pipeline.transcribe()"
    to: "BackendRegistry.get_backend"
    via: "backend retrieval"
    pattern: "get_backend(backend_type) → TranscriptionBackend"
    
  - from: "Pipeline.transcribe()"
    to: "backend.transcribe"
    via: "transcription"
    pattern: "backend.transcribe(audio_path, options) → TranscriptionResult"
    
  - from: "Pipeline.transcribe()"
    to: "format_text / format_json"
    via: "output formatting"
    pattern: "format_[format](result, options) → str"
    
  - from: "Pipeline.transcribe()"
    to: "temp_audio_file"
    via: "cleanup context manager"
    pattern: "with temp_audio_file() as audio_path: ... # guaranteed cleanup"
    
  - from: "ProgressCallback"
    to: "Pipeline"
    via: "event emission"
    pattern: "callback(stage, progress, message) → user-defined handler"
    
  - from: "CancellationToken"
    to: "Pipeline"
    via: "cancellation check"
    pattern: "if token.is_cancelled: raise CancelledError()"
```

## Plan Breakdown

### Plan 09-01: Pipeline Orchestrator Implementation

**Objective:** Implement the main Pipeline class that coordinates media loading, VAD, backend selection, transcription, and result assembly.

**Wave:** 1 (Foundation layer, establishes core orchestration)

**Autonomous:** true

**Requirements:** PIPE-01

**Files Modified:**
- `src/audiocore/pipeline/__init__.py` (new)
- `src/audiocore/pipeline/orchestrator.py` (new)
- `src/audiocore/__init__.py` (modified - export transcribe)
- `tests/unit/pipeline/__init__.py` (new)
- `tests/unit/pipeline/test_orchestrator.py` (new)

**Task Breakdown:**

<task type="auto">
  <name>Task 1: Create pipeline module structure</name>
  <files>src/audiocore/pipeline/__init__.py</files>
  <action>Create the pipeline module with Pipeline class skeleton. Import orchestration components (probe, extract_audio, detect_speech, BackendSelector, BackendRegistry). Define PipelineStage enum for stage tracking. Create PipelineConfig model that wraps AppConfig and TranscriptionOptions. No business logic yet — just structure and imports.</action>
  <verify>pytest tests/unit/pipeline/ -v --collect-only shows tests collected</verify>
  <done>Module imports work, Pipeline class exists, PipelineStage enum defined</done>
</task>

<task type="auto">
  <name>Task 2: Implement Pipeline.transcribe orchestration</name>
  <files>src/audiocore/pipeline/orchestrator.py</files>
  <action>Implement the full transcribe(path, options) method that:
  1. Validates input format using validate_format_or_raise
  2. Probes media with probe(path) to get MediaInfo
  3. Extracts audio to temp file using extract_audio with temp_audio_file context manager
  4. Runs VAD with detect_speech(audio_path, config, duration) to segment audio
  5. Selects backend using BackendSelector(backend, policy).select()
  6. Gets backend instance via BackendRegistry.get_backend()
  7. Calls backend.transcribe(audio_path, options) for each segment (or whole file if no VAD)
  8. Merges segment results into final TranscriptionResult
  9. Returns TranscriptionResult with all metadata
  Use context managers for temp file cleanup. Raise typed exceptions on failures.</action>
  <verify>pytest tests/unit/pipeline/test_orchestrator.py -v passes (mock backend/VAD)</verify>
  <done>Pipeline coordinates all components, returns TranscriptionResult, cleans up temp files on success</done>
</task>

<task type="auto">
  <name>Task 3: Add convenience transcribe function</name>
  <files>src/audiocore/__init__.py, src/audiocore/pipeline/orchestrator.py</files>
  <action>Create top-level transcribe(path, options=None) function that creates Pipeline instance and calls transcribe. This provides the simplest API: from audiocore import transcribe; result = transcribe("audio.mp3"). Export from audiocore.__init__.py. Add convenience function tests.</action>
  <verify>pytest tests/unit/pipeline/test_orchestrator.py::test_transcribe_convenience_function -v passes</verify>
  <done>transcribe() function works, users can import from audiocore directly</done>
</task>

<task type="auto">
  <name>Task 4: Write comprehensive unit tests</name>
  <files>tests/unit/pipeline/test_orchestrator.py</files>
  <action>Create unit tests for Pipeline.transcribe that mock all dependencies:
  - test_transcribe_calls_validate_format
  - test_transcribe_calls_probe
  - test_transcribe_calls_extract_audio
  - test_transcribe_calls_detect_speech
  - test_transcribe_selects_backend_automatically
  - test_transcribe_uses_provided_backend
  - test_transcribe_merges_segment_results
  - test_transcribe_cleans_up_temp_files_on_success
  - test_transcribe_cleans_up_temp_files_on_failure
  - test_transcribe_raises_typed_exceptions
  Use pytest fixtures to create mock backends, mock VAD, mock media components. Target >95% coverage.</action>
  <verify>pytest tests/unit/pipeline/test_orchestrator.py --cov=src/audiocore/pipeline --cov-report=term-missing shows >95% coverage</verify>
  <done>All pipeline orchestration paths tested, mocks verify component calls, >95% coverage achieved</done>
</task>

---

### Plan 09-02: Progress Callbacks and Cancellation

**Objective:** Implement progress callbacks for stage notifications and cancellation support for clean pipeline termination.

**Wave:** 2 (Depends on Plan 09-01 for Pipeline class)

**Autonomous:** true

**Requirements:** PIPE-02

**Files Modified:**
- `src/audiocore/pipeline/progress.py` (new)
- `src/audiocore/pipeline/cancellation.py` (new)
- `src/audiocore/pipeline/orchestrator.py` (modified)
- `src/audiocore/pipeline/__init__.py` (modified)
- `tests/unit/pipeline/test_progress.py` (new)
- `tests/unit/pipeline/test_cancellation.py` (new)

**Task Breakdown:**

<task type="auto">
  <name>Task 1: Define progress callback types</name>
  <files>src/audiocore/pipeline/progress.py</files>
  <action>Create PipelineStage enum (PROBING, EXTRACTING, VAD, SELECTING, TRANSCRIBING, FORMATTING, COMPLETE) and ProgressCallback Protocol with __call__(stage: PipelineStage, progress: float, message: str) method. Create ProgressEvent dataclass for event emission. Define callback interface that matches existing progress_callback patterns from extract_audio.</action>
  <verify>pytest tests/unit/pipeline/test_progress.py::test_progress_types -v passes</verify>
  <done>ProgressCallback Protocol and PipelineStage enum defined, types import correctly</done>
</task>

<task type="auto">
  <name>Task 2: Implement cancellation token</name>
  <files>src/audiocore/pipeline/cancellation.py</files>
  <action>Create CancellationToken class with:
  - is_cancelled: bool property
  - cancel(): void method to set cancelled state
  - check(): raises CancelledError if cancelled (used in long operations)
  Create CancelledError exception that inherits from AudioCoreError. Thread-safe implementation using threading.Event.</action>
  <verify>pytest tests/unit/pipeline/test_cancellation.py -v passes</verify>
  <done>CancellationToken works, threadsafe, CancelledError raised correctly</done>
</task>

<task type="auto">
  <name>Task 3: Integrate progress callbacks into Pipeline</name>
  <files>src/audiocore/pipeline/orchestrator.py</files>
  <action>Modify Pipeline.transcribe to accept optional progress_callback and cancellation_token parameters. Emit progress events at each stage transition:
  - PROBING: probe(path)
  - EXTRACTING: extract_audio with progress_callback
  - VAD: detect_speech
  - SELECTING: select_backend
  - TRANSCRIBING: backend.transcribe
  - FORMATTING: output formatting
  - COMPLETE: final result
Check cancellation token after each stage and raise CancelledError if cancelled. Ensure cleanup happens even on cancellation.</action>
  <verify>pytest tests/unit/pipeline/test_progress.py::test_progress_callbacks_emitted -v passes</verify>
  <done>Progress callbacks fire at each stage, cancellation stops pipeline cleanly</done>
</task>

<task type="auto">
  <name>Task 4: Write progress and cancellation tests</name>
  <files>tests/unit/pipeline/test_progress.py, tests/unit/pipeline/test_cancellation.py</files>
  <action>Create comprehensive tests for:
  - Progress callback invocation at each stage
  - Progress percentage updates during extraction
  - Cancellation token cancel() and is_cancelled
  - CancelledError raised when cancellation detected
  - Pipeline cleanup on cancellation
  - Thread-safe cancellation from another thread
Use mock callbacks and capture all event emissions. Target >95% coverage.</action>
  <verify>pytest tests/unit/pipeline/ --cov=src/audiocore/pipeline/progress --cov=src/audiocore/pipeline/cancellation --cov-report=term-missing shows >95% coverage</verify>
  <done>All progress and cancellation paths tested, callback events verified, cancellation cleanup confirmed</done>
</task>

---

### Plan 09-03: Plain Text and JSON Output Serializers

**Objective:** Implement output formatters for plain text (timestamped) and JSON formats.

**Wave:** 2 (Independent of Plan 09-02, can run parallel)

**Autonomous:** true

**Requirements:** OUT-01, OUT-02

**Files Modified:**
- `src/audiocore/output/__init__.py` (new)
- `src/audiocore/output/text.py` (new)
- `src/audiocore/output/json.py` (new)
- `src/audiocore/pipeline/orchestrator.py` (modified - use formatters)
- `tests/unit/output/__init__.py` (new)
- `tests/unit/output/test_text.py` (new)
- `tests/unit/output/test_json.py` (new)

**Task Breakdown:**

<task type="auto">
  <name>Task 1: Create output module and text formatter</name>
  <files>src/audiocore/output/__init__.py, src/audiocore/output/text.py</files>
  <action>Create output module. Implement format_text(result: TranscriptionResult, options: TranscriptionOptions) function that produces timestamped text output:
  - Each segment on its own line: [HH:MM:SS.mmm] text
  - Timestamps formatted as HH:MM:SS.mmm (zero-padded)
  - Text segments concatenated with newlines
  - Empty text segments handled gracefully
  - UTF-8 encoding guaranteed
Export format_text from output module.</action>
  <verify>pytest tests/unit/output/test_text.py -v passes</verify>
  <done>Text formatter produces correct timestamped output, empty segments handled</done>
</task>

<task type="auto">
  <name>Task 2: Create JSON formatter</name>
  <files>src/audiocore/output/json.py</files>
  <action>Implement format_json(result: TranscriptionResult, options: TranscriptionOptions, indent: int | None = 2) function that produces structured JSON:
  - Full transcription result with metadata
  - Segments array with all fields (start_time, end_time, text, confidence)
  - Configuration used (model, backend, language)
  - Processing duration
  - Backend used
  - Use Pydantic model_dump() for serialization
  - Ensure all types JSON-serializable (datetime, enum, Path converted)
Export format_json from output module.</action>
  <verify>pytest tests/unit/output/test_json.py -v passes</verify>
  <done>JSON formatter produces valid JSON with all metadata, enums serialized correctly</done>
</task>

<task type="auto">
  <name>Task 3: Integrate formatters into Pipeline</name>
  <files>src/audiocore/pipeline/orchestrator.py</files>
  <action>Modify Pipeline to use output formatters based on TranscriptionOptions.output_format:
  - OutputFormat.TEXT → format_text()
  - OutputFormat.JSON → format_json()
  - Store formatted output in TranscriptionResult (or add output_text/output_json fields)
  - Emit FORMATTING progress stage before calling formatter
  - Return result with both raw segments and formatted output</action>
  <verify>pytest tests/unit/pipeline/test_orchestrator.py::test_transcribe_uses_text_formatter -v passes</verify>
  <done>Pipeline uses correct formatter based on output_format, formatted output available</done>
</task>

<task type="auto">
  <name>Task 4: Write formatter unit tests</name>
  <files>tests/unit/output/test_text.py, tests/unit/output/test_json.py</files>
  <action>Create comprehensive tests for text and JSON formatters:
  - Text: multiple segments, empty text, special characters, timestamps formatting
  - JSON: full result serialization, nested objects, enum serialization, minification option
  - Both: UTF-8 encoding, round-trip parsing (JSON parseable, text parseable to segments)
Use fixtures for sample TranscriptionResult and Segment objects. Target >95% coverage.</action>
  <verify>pytest tests/unit/output/ --cov=src/audiocore/output --cov-report=term-missing shows >95% coverage</verify>
  <done>All formatter paths tested, edge cases covered, >95% coverage achieved</done>
</task>

---

### Plan 09-04: Pipeline Error Recovery and Cleanup

**Objective:** Implement comprehensive error handling, partial result preservation, and guaranteed cleanup with context managers.

**Wave:** 3 (Depends on Plans 09-01, 09-02, 09-03 for full pipeline)

**Autonomous:** true

**Requirements:** PIPE-03, ERR-03

**Files Modified:**
- `src/audiocore/pipeline/orchestrator.py` (modified)
- `src/audiocore/pipeline/errors.py` (new)
- `src/audiocore/errors/__init__.py` (modified)
- `tests/unit/pipeline/test_error_recovery.py` (new)

**Task Breakdown:**

<task type="auto">
  <name>Task 1: Define pipeline-specific exceptions</name>
  <files>src/audiocore/pipeline/errors.py, src/audiocore/errors/__init__.py</files>
  <action>Create PipelineError exception that inherits from AudioCoreError:
  - PipelineError with error_code AUD-500 series
  - PipelineStageError for stage-specific failures (wraps underlying exception)
  - PipelineCancelledError for cancellation
  - PartialResultError for failures with partial data
Each exception carries stage (PROBING, EXTRACTING, etc.), original_error, and partial_result (if available). Export from errors module.</action>
  <verify>pytest tests/unit/pipeline/test_error_recovery.py::test_pipeline_exceptions -v passes</verify>
  <done>Pipeline-specific exceptions defined, error codes assigned, inherits from AudioCoreError</done>
</task>

<task type="auto">
  <name>Task 2: Implement temp file cleanup with context managers</name>
  <files>src/audiocore/pipeline/orchestrator.py</files>
  <action>Refactor Pipeline.transcribe to use nested context managers for guaranteed cleanup:
  1. Use temp_audio_file context manager for extracted audio
  2. Add try/finally blocks for each stage
  3. Track created temp files in list
  4. Cleanup in finally block even on cancellation or error
  5. Log cleanup actions at debug level
Ensure cleanup happens in this order: temp audio files, then return or raise.</action>
  <verify>pytest tests/unit/pipeline/test_error_recovery.py::test_temp_file_cleanup_on_success -v passes</verify>
  <done>Temp files cleaned up on success, failure, and cancellation</done>
</task>

<task type="auto">
  <name>Task 3: Implement partial result preservation for ERR-03</name>
  <files>src/audiocore/pipeline/orchestrator.py</files>
  <action>Modify Pipeline to preserve partial results when failures occur:
  - If VAD fails, try whole-file transcription (fallback)
  - If segment transcription fails, collect successful segments and mark failed ones
  - Add failed_segments list to TranscriptionResult for partial transcriptions
  - Log warnings for partial issues at WARNING level
  - Raise PartialResultError with partial TranscriptionResult attached
Wrap underlying exceptions (MediaError, VADError, BackendError) in PipelineStageError with stage context.</action>
  <verify>pytest tests/unit/pipeline/test_error_recovery.py::test_partial_result_on_transcription_failure -v passes</verify>
  <done>Partial results preserved on failure, VAD fallback works, failed segments tracked</done>
</task>

<task type="auto">
  <name>Task 4: Write error recovery and cleanup tests</name>
  <files>tests/unit/pipeline/test_error_recovery.py</files>
  <action>Create comprehensive tests for error handling:
  - test_cleanup_on_probe_failure
  - test_cleanup_on_extraction_failure
  - test_cleanup_on_vad_failure
  - test_cleanup_on_backend_failure
  - test_cleanup_on_cancellation
  - test_partial_result_preserved
  - test_vad_fallback_to_whole_file
  - test_segment_failure_collects_successful
  - test_user_friendly_error_messages
Use mock components that raise exceptions at different stages. Verify cleanup happens in all cases. Target >95% coverage.</action>
  <verify>pytest tests/unit/pipeline/test_error_recovery.py --cov=src/audiocore/pipeline --cov-report=term-missing shows >95% coverage for error paths</verify>
  <done>All error paths tested, cleanup verified in all scenarios, partial preservation works</done>
</task>

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

From `src/audiocore/types/format.py`:
```python
class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    SRT = "srt"
    VTT = "vtt"
```

From `src/audiocore/types/policy.py`:
```python
class SelectionPolicy(str, Enum):
    PREFER_LOCAL = "prefer_local"
    PREFER_CLOUD = "prefer_cloud"
    AUTO = "auto"
```

From `src/audiocore/types/backend.py`:
```python
class BackendType(str, Enum):
    OPENAI = "openai"
    FASTER_WHISPER = "faster_whisper"
    AUTO = "auto"
```

From `src/audiocore/models/transcription.py`:
```python
class TranscriptionOptions(BaseModel):
    language: str | None = None
    model_size: ModelSize = ModelSize.BASE
    backend: BackendType = BackendType.AUTO
    output_format: OutputFormat = OutputFormat.TEXT
    backend_preference: SelectionPolicy = SelectionPolicy.AUTO

class TranscriptionResult(BaseModel):
    segments: list[Segment]
    media_info: MediaInfo
    config_used: TranscriptionOptions
    duration_seconds: float
    backend_used: BackendType
```

From `src/audiocore/models/segment.py`:
```python
class Segment(BaseModel):
    start_time: float  # Start time in seconds
    end_time: float    # End time in seconds
    text: str = ""     # Transcription text
    confidence: float | None = None  # VAD/ASR confidence
```

From `src/audiocore/models/media.py`:
```python
class MediaInfo(BaseModel):
    path: Path
    duration: float
    format: str
    codec: str | None = None
    sample_rate: int | None = None
    channels: int | None = None
```

From `src/audiocore/media/__init__.py`:
```python
def probe(path: str | Path) -> MediaInfo: ...
def extract_audio(input_path: str | Path, output_path: str | Path, progress_callback: Callable[[float], None] | None = None) -> Path: ...
@contextmanager
def temp_audio_file(suffix: str = ".wav") -> Path: ...
def validate_format_or_raise(path: str | Path) -> None: ...  # Raises MediaFormatError
```

From `src/audiocore/vad/__init__.py`:
```python
def detect_speech(audio_path: str | Path, config: VADConfig | None = None, total_duration: float | None = None) -> list[Segment]: ...
```

From `src/audiocore/backends/selector.py`:
```python
class BackendSelector:
    def select(self, backend: BackendType = BackendType.AUTO, policy: SelectionPolicy = SelectionPolicy.AUTO) -> BackendType: ...
    def get_backend(self, backend: BackendType) -> TranscriptionBackend: ...
```

From `src/audiocore/backends/base.py`:
```python
class TranscriptionBackend(ABC):
    @property
    @abstractmethod
    def backend_type(self) -> BackendType: ...
    
    @abstractmethod
    def is_available(self) -> bool: ...
    
    @abstractmethod
    def transcribe(self, audio_path: Path | str, options: TranscriptionOptions) -> TranscriptionResult: ...
    
    @abstractmethod
    def get_name(self) -> str: ...
```

From `src/audiocore/config/__init__.py`:
```python
class AppConfig(BaseSettings):
    openai: OpenAIConfig
    faster_whisper: FasterWhisperConfig
    vad: VADConfig
    # ... other config fields
```

From `src/audiocore/errors/__init__.py`:
```python
class AudioCoreError(Exception):
    error_code: str
    message: str
    context: dict
    suggestions: list[str]

class MediaError(AudioCoreError): ...
class MediaFormatError(MediaError): ...
class VADError(AudioCoreError): ...
class BackendError(AudioCoreError): ...
class BackendUnavailableError(BackendError): ...
class TranscriptionError(AudioCoreError): ...
```
</interfaces>

## Verification Criteria

### Per-Plan Verification

**Plan 09-01:**
- [ ] Pipeline module created with correct structure
- [ ] Pipeline.transcribe() method orchestrates all components
- [ ] Format validation raises MediaFormatError for unsupported formats
- [ ] Media probing and audio extraction called correctly
- [ ] VAD integration works with detect_speech
- [ ] Backend auto-selection works via BackendSelector
- [ ] Backend retrieval via BackendRegistry works
- [ ] Transcription called with correct parameters
- [ ] TranscriptionResult returned with full metadata
- [ ] Temp file cleanup on success
- [ ] All unit tests pass (>95% coverage)

**Plan 09-02:**
- [ ] ProgressCallback Protocol defined with stage, progress, message
- [ ] PipelineStage enum covers all stages (PROBING through COMPLETE)
- [ ] CancellationToken with cancel(), is_cancelled, check()
- [ ] CancelledError raised when cancellation detected
- [ ] Progress callbacks emitted at each stage
- [ ] Cancellation stops pipeline cleanly
- [ ] Cleanup happens even on cancellation
- [ ] All unit tests pass (>95% coverage)

**Plan 09-03:**
- [ ] Text formatter produces [HH:MM:SS.mmm] text format
- [ ] JSON formatter produces valid JSON with metadata
- [ ] Pipeline uses formatters based on output_format
- [ ] UTF-8 encoding guaranteed
- [ ] Empty segments handled gracefully
- [ ] All unit tests pass (>95% coverage)

**Plan 09-04:**
- [ ] Pipeline-specific exceptions defined (AUD-500 series)
- [ ] Temp file cleanup with context managers
- [ ] Cleanup on success, failure, cancellation
- [ ] Partial result preservation for transcription failures
- [ ] VAD fallback to whole-file on VAD failure
- [ ] User-friendly error messages with context
- [ ] All unit tests pass (>95% coverage)

### Phase Success Criteria

**Goal Achievement:** User can run full pipeline with auto-selection, progress, cancellation, and output formatting.

**Measurable Truths:**
1. ✅ `transcribe("audio.mp3")` returns TranscriptionResult without any manual steps
2. ✅ Progress callback receives events at each stage with percentage updates
3. ✅ CancellationToken.cancel() stops pipeline and cleans up temp files
4. ✅ Pipeline failures clean up temp files via context managers
5. ✅ Partial transcription results available via API on segment failures
6. ✅ `format_text(result)` produces `[HH:MM:SS.mmm] text` lines
7. ✅ `format_json(result)` produces parseable JSON with metadata
8. ✅ AUTO backend selection chooses correct backend based on availability
9. ✅ Unsupported formats raise MediaFormatError before processing
10. ✅ All stages have typed exceptions with actionable guidance

**Coverage Requirements:**
- Pipeline orchestrator: >95% coverage
- Progress callbacks: >95% coverage
- Cancellation: >95% coverage
- Output formatters: >95% coverage
- Error recovery: >95% coverage for error paths

## Risk Mitigation

### Phase Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Temp file leak on failure | Medium | High | Context managers with try/finally for guaranteed cleanup |
| Cancellation race conditions | Low | Medium | Thread-safe CancellationToken with threading.Event |
| Progress callback performance | Low | Low | Callback made optional, no default implementation |
| Partial result completeness | Medium | Medium | Track failed segments separately, log warnings |
| Format edge cases | Low | Low | Comprehensive edge case tests (empty text, special chars) |

### Technical Considerations

1. **Context Manager Pattern:**
   - Use `temp_audio_file()` context manager for all temp files
   - Nested context managers for multiple resources
   - Ensure exceptions don't bypass cleanup

2. **Cancellation Threading:**
   - CancellationToken uses threading.Event for thread safety
   - Check cancellation at stage boundaries, not mid-operation
   - CancelledError inherits from AudioCoreError for consistent handling

3. **Progress Callback Design:**
   - Make progress_callback optional parameter (default None)
   - Check `if progress_callback:` before calling
   - Don't block on callback execution

4. **Partial Results:**
   - Add optional `failed_segments` field to TranscriptionResult
   - Preserve successfully transcribed segments
   - Mark partial results with warning in logs

5. **Output Formatting:**
   - Formatters are pure functions (no side effects)
   - Always use UTF-8 encoding
   - JSON uses Pydantic model_dump() for serialization

## Implementation Notes

### Pattern Consistency

Follow existing patterns from Phase 6/7/8:
- Use Pydantic models for all data structures
- Raise typed exceptions with context and suggestions
- Use context managers for resource cleanup
- Lazy imports for optional dependencies
- Thread-safe singletons where needed (CancellationToken)

### Pipeline Stage Order

```
1. VALIDATE  ───► validate_format_or_raise(path)
2. PROBE     ───► probe(path) ──> MediaInfo
3. EXTRACT   ───► extract_audio(input, temp, progress)
4. VAD       ───► detect_speech(audio, config, duration)
5. SELECT    ───► select_backend(backend, policy)
6. TRANSCRIBE───► backend.transcribe(audio, options)
7. MERGE     ───► merge segment results
8. FORMAT    ───► format_text/format_json(result)
9. CLEANUP   ───► delete temp files
10. RETURN   ───► TranscriptionResult
```

### Error Handling Strategy

```
VALIDATE fails  ──► MediaFormatError (no cleanup needed)
PROBE fails      ──► MediaError (no temp files)
EXTRACT fails    ──► MediaError + cleanup temp
VAD fails        ──► VADError + fallback to whole-file + cleanup
SELECT fails     ──► BackendUnavailableError + cleanup temp
TRANSCRIBE fails ──► BackendError + partial result + cleanup temp
FORMAT fails     ──► TranscriptionError (result still valid) + cleanup
```

### Concurrency Considerations

- Pipeline is NOT thread-safe by default
- CancellationToken provides thread-safe cancellation
- Multiple pipelines can run concurrently in separate threads
- BackendRegistry is thread-safe for concurrent backend access

## Next Steps

After planning approval:
1. Execute Plan 09-01 (Pipeline Orchestrator Implementation)
2. Execute Plan 09-02 (Progress Callbacks and Cancellation) - can run parallel with 09-03
3. Execute Plan 09-03 (Output Formatters) - can run parallel with 09-02
4. Execute Plan 09-04 (Error Recovery and Cleanup) - must run after 09-01, 09-02, 09-03
5. Verify all success criteria met
6. Run integration tests with real audio files
7. Update STATE.md with completion notes