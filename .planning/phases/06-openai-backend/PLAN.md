# Phase 6: OpenAI Backend

## Goal Statement

Implement production-ready OpenAI Whisper API integration with complete error handling, API key validation, and backend abstraction compliance. The OpenAI backend enables cloud-based transcription with configurable parameters and robust error recovery.

**Purpose:** Provide a fully-featured OpenAI Whisper API backend that implements the TranscriptionBackend interface, handles all API error types gracefully, and protects API keys from exposure.

**Output:** OpenAIBackend class ready for use via BackendRegistry, with comprehensive test coverage validating transcription, error handling, and key protection.

---

## Requirements Mapping

| Requirement ID | Requirement | Plan Coverage |
|---------------|-------------|---------------|
| OPEN-01 | OpenAI Whisper API Client | Plan 1 |
| OPEN-02 | OpenAI Configuration Options | Plan 2 |
| OPEN-03 | OpenAI Error Handling and Key Protection | Plan 3 |

---

## Dependency Analysis

### Internal Dependencies (Phases 1-5)

| Phase | Dependency | How It's Used |
|-------|------------|---------------|
| Phase 1 | Exception hierarchy (AudioCoreError, APIError, etc.) | Raise typed exceptions for all OpenAI errors |
| Phase 1 | Domain models (Segment, TranscriptionResult, TranscriptionOptions, MediaInfo) | Return structured results, accept configuration |
| Phase 2 | Configuration system (AppConfig, SecretStr for API keys) | Read OpenAI API key from config |
| Phase 5 | TranscriptionBackend ABC (backend_type, transcribe, get_name, is_available, get_model_options) | Implement backend interface |
| Phase 5 | BackendRegistry (register, get_backend, list_backends) | Register OpenAI backend for discovery |
| Phase 5 | BackendUnavailableError | Raise when backend unavailable |
| Phase 5 | BackendError, TranscriptionError | Raise for transcription failures |

### Cross-Phase Dependencies (Future Phases)

| Future Phase | Dependency | How It's Used |
|-------------|------------|---------------|
| Phase 8 | Backend selection | BackendRegistry.get_backend(BackendType.OPENAI) |
| Phase 9 | Pipeline orchestration | Backend.transcribe() called by orchestrator |
| Phase 10 | CLI/API | Backend discovered via registry and used for transcription |

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `openai` | ^1.0.0 | Official OpenAI Python SDK |
| `httpx` | ^0.27.0 | HTTP client (openai dependency) |

---

## Task Breakdown

### Plan 1: OpenAI Client Implementation (06-01)

**Wave:** 1 (independent - foundation for Plan 2 & 3)

**Files:**
- `src/audiocore/backends/openai_backend.py` — Main OpenAI backend implementation
- `src/audiocore/backends/__init__.py` — Module exports (update)
- `tests/unit/backends/test_openai_backend.py` — Unit tests
- `tests/unit/backends/__init__.py` — Test module init (create if needed)

**Must-Haves (Goal-Backward Derivation):**
- **Truth:** User can transcribe audio via OpenAI Whisper API
- **Truth:** API key is validated before transcription attempt
- **Truth:** Backend implements all TranscriptionBackend ABC methods
- **Truth:** All OpenAI API errors convert to typed AudioCore exceptions
- **Artifact:** `src/audiocore/backends/openai_backend.py` implementing OpenAIBackend
- **Key Link:** OpenAIBackend.transcribe() → openai.Audio.transcribe() → TranscriptionResult

**Tasks:**

#### Task 1.1: Create OpenAIBackend Class Skeleton

**Type:** `auto`

**Files:** `src/audiocore/backends/openai_backend.py`

**Action:**
Create OpenAIBackend class implementing TranscriptionBackend ABC with all required methods:
1. Import openai SDK, TranscriptionBackend from base.py, required types (BackendType, TranscriptionOptions, TranscriptionResult, Segment, MediaInfo)
2. Import all API error types from audiocore.errors.api (AuthenticationError, RateLimitError, APITimeoutError, APIError)
3. Import BackendUnavailableError, TranscriptionError from audiocore.errors.backend
4. Define OpenAIBackend class inheriting from TranscriptionBackend
5. Implement @property backend_type() → BackendType.OPENAI
6. Implement get_name() → "OpenAI Whisper API"
7. Implement get_model_options() → ["whisper-1"] (OpenAI only has one model)
8. Implement is_available() → check if API key is configured (use openai.api_key check)
9. Create placeholder transcribe() method raising NotImplementedError for next task

**Verify:**
```bash
pytest tests/unit/backends/test_openai_backend.py -xvs -k "test_skeleton"
```

**Done:**
- OpenAIBackend class defined with all ABC methods
- backend_type returns BackendType.OPENAI
- get_name returns "OpenAI Whisper API"
- get_model_options returns ["whisper-1"]
- is_available checks API key presence
- All imports resolve without circular dependencies

---

#### Task 1.2: Implement Transcribe Method Core

**Type:** `auto`

**Files:** `src/audiocore/backends/openai_backend.py`, `tests/unit/backends/test_openai_backend.py`

**Action:**
Implement transcribe() method with OpenAI API integration:
1. Validate audio_path exists and is readable (Path conversion, file check)
2. Read API key from openai.api_key (set during config initialization in Plan 2)
3. Call openai.Audio.transcribe() with model="whisper-1" and options parameters:
   - file: open audio file in binary mode
   - model: "whisper-1"
   - language: options.language if provided
   - temperature: Map options.model_size to temperature (tiny=0.0, base=0.2, small=0.4, medium=0.6, large=0.8) - or use config
   - response_format: "verbose_json" to get segments with timestamps
4. Parse OpenAI response into Segments with start_time, end_time, text extracted from response
5. Build MediaInfo from file (simple: duration from response or calculate from last segment end_time)
6. Build TranscriptionResult with segments, media_info, config_used=options, duration_seconds, backend_used=BackendType.OPENAI
7. Return TranscriptionResult

**Implementation Notes:**
- OpenAI Whisper API response format for verbose_json includes: text (full), segments (list with start, end, text)
- Duration can be extracted from last segment's end_time or from response metadata
- Use time.time() to capture start/end for duration_seconds calculation
- Use context manager for file opening to ensure cleanup

**Verify:**
```bash
pytest tests/unit/backends/test_openai_backend.py -xvs -k "test_transcribe"
```

**Done:**
- transcribe() method accepts audio_path and TranscriptionOptions
- Opens and reads audio file in binary mode
- Makes OpenAI API call with correct parameters
- Parses response into TranscriptionResult with Segments
- Returns TranscriptionResult with all required fields
- File handles properly closed

---

#### Task 1.3: Implement Error Handling Wrapper

**Type:** `auto`

**Files:** `src/audiocore/backends/openai_backend.py`, `tests/unit/backends/test_openai_backend.py`

**Action:**
Wrap transcribe() in comprehensive error handling:
1. Wrap transcribe() call in try/except block
2. Map OpenAI exceptions to AudioCore exceptions:
   - openai.AuthenticationError → AuthenticationError (context: backend="openai", suggestions=["Verify API key at https://platform.openai.com/api-keys"])
   - openai.RateLimitError → RateLimitError (context: backend="openai", extract retry_after if available)
   - openai.APITimeoutError → APITimeoutError (context: backend="openai")
   - openai.APIError → APIError (context: backend="openai", cause=original)
   - openai.APIConnectionError → APIError (context: backend="openai", suggestions=["Check network connectivity"])
   - Other openai.OpenAIError → TranscriptionError (context: backend="openai", cause=original)
3. Always redact API key from error messages using str.replace(api_key, "[REDACTED]")
4. Preserve __cause__ chain on all exceptions for debugging
5. Add logging at DEBUG level for all API calls (without API key in log message)

**Implementation Notes:**
- OpenAI SDK v1.0+ uses openai.AuthenticationError, openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.APIError
- API key can be accessed from openai.api_key for redaction
- Use logger = logging.getLogger(__name__) at module level
- Only redact if API key exists (not None/empty)

**Verify:**
```bash
pytest tests/unit/backends/test_openai_backend.py -xvs -k "test_error"
```

**Done:**
- All OpenAI exception types mapped to AudioCore exceptions
- API key redacted from ALL error messages and context dicts
- Exception chain preserved with __cause__
- Debug logging for API calls (no API key in logs)
- Error messages are actionable and user-friendly

---

### Plan 2: OpenAI Configuration (06-02)

**Wave:** 2 (depends on Plan 1 for backend integration, depends on Phase 2 config system)

**Files:**
- `src/audiocore/config/openai_config.py` — OpenAI-specific configuration model
- `src/audiocore/config/__init__.py` — Module exports (update)
- `tests/unit/config/test_openai_config.py` — Unit tests

**Must-Haves (Goal-Backward Derivation):**
- **Truth:** User can configure OpenAI API key via environment variable
- **Truth:** User can configure OpenAI-specific parameters (temperature, prompt hints)
- **Truth:** API key is never logged or exposed in output
- **Truth:** Configuration integrates with existing AppConfig
- **Artifact:** `src/audiocore/config/openai_config.py` with OpenAIConfig model
- **Key Link:** OpenAIConfig.openai_api_key → openai.api_key assignment (in backend initialization)

**Tasks:**

#### Task 2.1: Create OpenAIConfig Pydantic Model

**Type:** `auto`

**Files:** `src/audiocore/config/openai_config.py`, `tests/unit/config/test_openai_config.py`

**Action:**
Create OpenAIConfig model with SecretStr for API key and OpenAI-specific parameters:
1. Define OpenAIConfig class inheriting from pydantic_settings.BaseSettings
2. Add openai_api_key: SecretStr field with description="OpenAI API key for Whisper transcription"
3. Add openai_model: str = "whisper-1" (only supported model)
4. Add openai_temperature: float = 0.0 (temperature for transcription, 0-1 range)
5. Add openai_language: str | None = None (language hint)
6. Add openai_prompt: str | None = None (prompt hint for better accuracy)
7. Field validation: openai_temperature must be between 0.0 and 1.0
8. model_config with env_prefix="AUDIOCORE_" for AUDIOCORE_OPENAI_API_KEY, AUDIOCORE_OPENAI_MODEL, etc.
9. Use model_config = {"str_strip_whitespace": True, "validate_assignment": True}
10. Ensure openai_api_key uses SecretStr to prevent __repr__ exposure

**Implementation Notes:**
- pydantic-settings handles environment variable reading automatically: AUDIOCORE_OPENAI_API_KEY → openai_api_key
- SecretStr.get_secret_value() retrieves the actual key for API calls
- Temperature 0.0 = deterministic output, higher = more variation

**Verify:**
```bash
pytest tests/unit/config/test_openai_config.py -xvs
```

**Done:**
- OpenAIConfig model defined with all OpenAI parameters
- API key stored as SecretStr
- Temperature validation enforces 0.0-1.0 range
- Environment variables map correctly (AUDIOCORE_OPENAI_API_KEY → openai_api_key)
- Validation errors are descriptive

---

#### Task 2.2: Integrate OpenAIConfig into AppConfig

**Type:** `auto`

**Files:** `src/audiocore/config/app_config.py` (update), `tests/unit/config/test_app_config.py` (update tests)

**Action:**
Add OpenAIConfig to existing AppConfig model:
1. Import OpenAIConfig from audiocore.config.openai_config
2. Add openai: OpenAIConfig = Field(default_factory=OpenAIConfig) to AppConfig
3. Update AppConfig.model_config to include nested env var support (pydantic-settings handles this automatically with env_nested_delimiter)
4. Update app_config fixture in tests if needed
5. Ensure API key redaction works in config display (already handled by SecretStr)

**Implementation Notes:**
- pydantic-settings automatically handles nested configs: AUDIOCORE_OPENAI__API_KEY (if env_nested_delimiter='__') or AUDIOCORE_OPENAI_API_KEY (flat)
- Check existing AppConfig for env_nested_delimiter configuration
- Field(default_factory=OpenAIConfig) creates a new instance with defaults

**Verify:**
```bash
pytest tests/unit/config/test_app_config.py -xvs -k "openai"
```

**Done:**
- OpenAIConfig nested within AppConfig
- Environment variable AUDIOCORE_OPENAI_API_KEY loads correctly
- Config display shows openai_api_key as SecretStr (redacted)
- AppConfig.openai.openai_api_key.get_secret_value() returns actual key

---

#### Task 2.3: Wire Configuration to Backend Initialization

**Type:** `auto`

**Files:** `src/audiocore/backends/openai_backend.py` (update), `tests/unit/backends/test_openai_backend.py` (update)

**Action:**
Connect OpenAIConfig to OpenAIBackend for API key setup:
1. Add optional config parameter to OpenAIBackend.__init__(self, config: OpenAIConfig | None = None)
2. If config provided: openai.api_key = config.openai_api_key.get_secret_value()
3. If no config: use existing openai.api_key (set manually or from environment)
4. Add check in is_available() to verify both openai.api_key is set AND key is valid format (starts with "sk-")
5. Store config reference in self._config for parameter defaults (temperature, prompt, language)
6. Update transcribe() to use self._config values as defaults, override with options parameter if provided
7. Add logging in __init__ indicating backend initialized with/without config

**Implementation Notes:**
- Allow config=None for manual API key setting (backwards compatibility for direct usage)
- is_available() should check: openai.api_key is not None and openai.api_key.startswith("sk-")
- Temperature: prefer options.model_size mapping OR config.openai_temperature
- Language: prefer options.language OR config.openai_language
- Prompt: use config.openai_prompt if set (not in TranscriptionOptions)

**Verify:**
```bash
pytest tests/unit/backends/test_openai_backend.py -xvs -k "test_config"
```

**Done:**
- OpenAIBackend accepts optional OpenAIConfig
- API key set from config on initialization
- is_available() validates API key format
- Default values pulled from config when options not provided
- Logging indicates initialization status

---

### Plan 3: Error Handling and Key Protection (06-03)

**Wave:** 3 (depends on Plan 1 and Plan 2 for full integration testing)

**Files:**
- `tests/integration/test_openai_backend_integration.py` — Integration tests (requires API key)
- `tests/fixtures/conftest.py` — Shared test fixtures (update)
- `docs/openai-setup.md` — Setup documentation (optional)

**Must-Haves (Goal-Backward Derivation):**
- **Truth:** All OpenAI error types testable without live API
- **Truth:** API key never appears in logs, exceptions, or string representations
- **Truth:** Backend properly registered with BackendRegistry
- **Truth:** Integration tests pass with live API (when key available)
- **Artifact:** Integration test file with comprehensive error scenarios
- **Key Link:** BackendRegistry.register(BackendType.OPENAI, OpenAIBackend) → get_backend(OPENAI)

**Tasks:**

#### Task 3.1: Write Comprehensive Unit Tests

**Type:** `auto`

**Files:** `tests/unit/backends/test_openai_backend.py`

**Action:**
Write unit tests for all OpenAI backend functionality using mocking:
1. Create test fixtures for mock OpenAI responses (successful transcription with segments)
2. Create test fixtures for all error types (AuthenticationError, RateLimitError, Timeout, Connection)
3. Test transcribe() success path with mocked openai.Audio.transcribe
4. Test transcribe() with missing API key (BackendUnavailableError)
5. Test transcribe() with each error type mapped to correct AudioCore exception
6. Test API key redaction in error messages (use dummy key "sk-test123", verify "[REDACTED]" in messages)
7. Test get_model_options() returns ["whisper-1"]
8. Test is_available() with/without API key
9. Test configuration integration (temperature, language, prompt from config)
10. Test SecretStr handling (verify __repr__ doesn't show key)

**Verify:**
```bash
pytest tests/unit/backends/test_openai_backend.py -xvs --cov=audiocore/backends/openai_backend --cov-report=term-missing
```

**Done:**
- 100% coverage of OpenAI backend unit tests
- All error types tested with mocked OpenAI responses
- API key redaction verified in all test cases
- Configuration integration tested
- No live API calls in unit tests (all mocked)

---

#### Task 3.2: Write Integration Tests

**Type:** `auto`

**Files:** `tests/integration/test_openai_backend_integration.py`

**Action:**
Write integration tests for live OpenAI API (requires API key):
1. Mark tests with @pytest.mark.integration and @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"))
2. Test real transcription with short sample audio (use tests/fixtures/test_audio.wav if exists, or create 1-second silence file)
3. Test transcribe() with different audio formats (mp3, wav - convert from test file if needed)
4. Test error handling with invalid API key (expect AuthenticationError)
5. Test rate limit handling (if possible - may need throttling or mock)
6. Test timeout handling (use very long audio or low timeout setting)
7. Verify TranscriptionResult structure matches expectations from live API
8. Test backend registration with registry and retrieval

**Implementation Notes:**
- Create tests/fixtures/test_audio.wav: a short 1-2 second audio file for testing
- Integration tests require OPENAI_API_KEY environment variable
- Skip integration tests in CI if no API key available
- Use pytest.mark.integration to separate from unit tests

**Verify:**
```bash
pytest tests/integration/test_openai_backend_integration.py -xvs -m integration
# Should skip if no OPENAI_API_KEY, otherwise run with live API
```

**Done:**
- Integration tests for real transcription
- Tests skip gracefully when no API key available
- Live API errors tested (invalid key, timeout)
- TranscriptionResult structure validated against real API
- Backend registry integration tested

---

#### Task 3.3: Register Backend and Validate Integration

**Type:** `auto`

**Files:** `src/audiocore/backends/__init__.py` (update), `tests/unit/backends/test_registry_integration.py` (create)

**Action:**
Register OpenAI backend with BackendRegistry and validate full integration:
1. In `src/audiocore/backends/__init__.py`: import OpenAIBackend from .openai_backend
2. Add auto-registration: `registry = BackendRegistry(); registry.register(BackendType.OPENAI, OpenAIBackend)`
3. Export OpenAIBackend in __all__ list
4. Create test file: `tests/unit/backends/test_registry_integration.py`
5. Test: BackendRegistry.get_backend(BackendType.OPENAI) returns OpenAIBackend instance
6. Test: BackendRegistry.list_backends() includes BackendType.OPENAI
7. Test: BackendRegistry.is_available(BackendType.OPENAI) returns correct availability
8. Test: Retrieved backend has correct backend_type property (BackendType.OPENAI)
9. Test: End-to-end: create config, get backend from registry, check is_available(), call get_name()

**Verify:**
```bash
pytest tests/unit/backends/test_registry_integration.py -xvs
```

**Done:**
- OpenAIBackend registered at module import time
- BackendRegistry.get_backend(OPENAI) returns OpenAI backend instance
- Registry lists OpenAI as available (when API key present)
- is_available() correctly reflects API key presence
- All registry methods work with OpenAI backend
- Clean import chain with no circular dependencies

---

## Verification Criteria

### Per-Plan Verification

**Plan 1 (OpenAI Client):**
- ✅ OpenAIBackend implements all TranscriptionBackend ABC methods
- ✅ transcribe() correctly calls OpenAI API and parses response
- ✅ All OpenAI errors mapped to AudioCore exceptions
- ✅ Unit tests pass with ≥95% coverage

**Plan 2 (Configuration):**
- ✅ OpenAIConfig integrates into AppConfig
- ✅ API key loaded from environment (AUDIOCORE_OPENAI_API_KEY)
- ✅ SecretStr prevents accidental key exposure
- ✅ is_available() validates API key format
- ✅ Configuration tests pass

**Plan 3 (Error Protection & Integration):**
- ✅ API key never in logs, errors, or __repr__
- ✅ Error messages redact API key
- ✅ Backend registered with BackendRegistry
- ✅ Integration tests pass (with API key) or skip gracefully

### Phase Success Criteria (Goal-Backward)

1. **User can transcribe audio using OpenAI Whisper API with configurable parameters**
   - ✅ OpenAIBackend.transcribe(audio_path, options) → TranscriptionResult
   - ✅ Temperature, language, prompt configurable via TranscriptionOptions or OpenAIConfig

2. **All OpenAI API errors convert to typed AudioCore exceptions with guidance**
   - ✅ AuthenticationError for invalid API key
   - ✅ RateLimitError with retry_after
   - ✅ APITimeoutError for network timeouts
   - ✅ APIError for server errors
   - ✅ TranscriptionError for other transcription failures

3. **API key is never logged or exposed in error messages**
   - ✅ SecretStr in OpenAIConfig
   - ✅ Redaction in all error messages
   - ✅ No API key in any log output
   - ✅ __repr__ shows SecretStr, not actual key

4. **Rate limits and network errors handled gracefully with retry capability**
   - ✅ RateLimitError includes retry_after context
   - ✅ APITimeoutError includes timeout context
   - ✅ Error messages include actionable guidance
   - ✅ Foundation for retry logic (actual retry in Phase 9 pipeline)

---

## Execution Context

<execution_context>
@/Users/seifreed/.config/opencode/get-shit-done/workflows/execute-plan.md
@/Users/seifreed/.config/opencode/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@src/audiocore/backends/base.py
@src/audiocore/backends/registry.py
@src/audiocore/errors/api.py
@src/audiocore/errors/backend.py
@src/audiocore/models/__init__.py
@src/audiocore/models/transcription.py
</context>

---

## Output

After each plan execution, create `.planning/phases/06-openai-backend/06-{NN}-SUMMARY.md` documenting:
- Tasks completed
- Files created/modified
- Tests passing
- Decisions made
- Integration points verified