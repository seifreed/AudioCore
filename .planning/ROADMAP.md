# Roadmap: AudioCore

## Overview

AudioCore delivers reliable audio/video transcription through a phased approach: foundation (models, config, errors) → media processing (ingestion, VAD) → backend infrastructure (abstraction, OpenAI, faster-whisper, selection) → pipeline orchestration → complete user interface (CLI, API, output formats). Each phase builds on the previous, delivering verifiable capabilities.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Core models, types, and error handling infrastructure (2026-03-24)
- [x] **Phase 2: Configuration System** - Environment and TOML configuration with priority chain (2026-03-24)
- [x] **Phase 3: Media Ingestion** - Audio extraction and format support via ffmpeg (2026-03-24)
- [x] **Phase 4: VAD Processing** - Voice activity detection and segmentation with Silero (2026-03-25)
- [x] **Phase 5: Backend Abstraction** - Backend interface and registry pattern (2026-03-25)
- [x] **Phase 6: OpenAI Backend** - Whisper API integration with error handling (2026-03-25)
- [x] **Phase 7: Faster-Whisper Backend** - Local transcription with model management (2026-03-25)
- [x] **Phase 8: Backend Selection** - Automatic and explicit backend selection policies (2026-03-25)
- [x] **Phase 9: Pipeline & Core Output** - Transcription orchestrator with text/JSON output (2026-03-25)
- [ ] **Phase 10: Complete Interface** - CLI, API, subtitle formats, and parallelism

## Phase Details

### Phase 1: Foundation
**Goal**: Establish type-safe domain model and comprehensive error handling infrastructure
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, ERR-01, ERR-02

**Success Criteria** (what must be TRUE):
1. Developer can import and use all core Pydantic models with IDE autocomplete
2. All domain enums (BackendType, OutputFormat, etc.) validate against incorrect values
3. All exceptions inherit from AudioCoreError with error codes
4. Exceptions carry context dict preserving original error information

**Plans**: 3 plans

Plans:
- [x] 01-01: Exception hierarchy with error codes and context (2026-03-24)
- [x] 01-02: Type enums and constants (2026-03-24)
- [x] 01-03: Core domain models with Pydantic validation (2026-03-24)

---

### Phase 2: Configuration System
**Goal**: Flexible configuration from environment, files, and defaults with clear priority
**Depends on**: Phase 1 (Foundation)
**Requirements**: CONF-01, CONF-02, CONF-03

**Success Criteria** (what must be TRUE):
1. User can configure all options via environment variables with AUDIOCORE_ prefix
2. TOML configuration file at ~/.config/audiocore/config.toml overrides defaults
3. Configuration priority chain works correctly: CLI > env > TOML > defaults
4. API keys are masked in logs and configuration display

**Plans**: 3 plans

Plans:
- [x] 02-01: Environment variable configuration loader (2026-03-24)
- [x] 02-02: TOML configuration file parser (2026-03-24)
- [x] 02-03: Configuration priority chain merger (2026-03-24)

---

### Phase 3: Media Ingestion
**Goal**: Reliable audio extraction from any media format with comprehensive probing
**Depends on**: Phase 1 (Foundation), Phase 2 (Configuration)
**Requirements**: MEDIA-01, MEDIA-02, MEDIA-03

**Success Criteria** (what must be TRUE):
1. User can probe any supported media file and get duration, format, codec info
2. Audio extraction produces 16kHz mono WAV suitable for transcription
3. Unsupported media formats raise MediaFormatError with actionable guidance
4. All standard formats work: mp3, wav, m4a, flac, ogg, aac, mp4, mkv, avi, mov, webm

**Plans**: 3 plans

Plans:
- [x] 03-01: Media probing with ffprobe (2026-03-24)
- [x] 03-02: Audio extraction with ffmpeg normalization (2026-03-24)
- [x] 03-03: Format validation and error handling (2026-03-24)

---

### Phase 4: VAD Processing
**Goal**: Intelligent audio segmentation using Silero VAD for improved transcription accuracy
**Depends on**: Phase 1 (Foundation), Phase 3 (Media Ingestion)
**Requirements**: VAD-01, VAD-02, VAD-03

**Success Criteria** (what must be TRUE):
1. Silero VAD model loads on first use and detects speech segments in audio
2. User can configure min/max segment duration and silence thresholds
3. VAD output converts to segment boundaries that maintain temporal order
4. Segments have no overlaps and cover entire audio without gaps beyond threshold

**Plans**: 3 plans

Plans:
- [x] 04-01: Silero VAD model integration (2026-03-25)
- [x] 04-02: VAD parameter configuration (2026-03-25)
- [x] 04-03: Segment boundary processing (2026-03-25)

---

### Phase 5: Backend Abstraction
**Goal**: Extensible backend interface supporting multiple transcription engines
**Depends on**: Phase 1 (Foundation)
**Requirements**: BACK-01, BACK-02

**Success Criteria** (what must be TRUE):
1. Developer can create new backend by implementing BackendInterface abstract methods
2. Backend registry lists all available backends and retrieves by type
3. All backends implement transcribe(audio_path, options) → TranscriptionResult
4. Backend availability check reports which backends are ready to use

**Plans**: 2 plans

Plans:
- [x] 05-01: Abstract backend interface definition (2026-03-25)
- [x] 05-02: Backend registry pattern implementation (2026-03-25)

---

### Phase 6: OpenAI Backend
**Goal**: Production-ready OpenAI Whisper API integration with complete error handling
**Depends on**: Phase 1 (Foundation), Phase 2 (Configuration), Phase 5 (Backend Abstraction)
**Requirements**: OPEN-01, OPEN-02, OPEN-03

**Success Criteria** (what must be TRUE):
1. User can transcribe audio using OpenAI Whisper API with configurable parameters
2. All OpenAI API errors convert to typed AudioCore exceptions with guidance
3. API key is never logged or exposed in error messages
4. Rate limits and network errors are handled gracefully with retry capability

**Plans**: 3 plans

Plans:
- [x] 06-01: OpenAI Whisper API client implementation (2026-03-25)
- [x] 06-02: OpenAI-specific configuration options (2026-03-25)
- [x] 06-03: OpenAI error handling and key protection (2026-03-25)

---

### Phase 7: Faster-Whisper Backend
**Goal**: High-quality local transcription with automatic model management
**Depends on**: Phase 1 (Foundation), Phase 2 (Configuration), Phase 5 (Backend Abstraction)
**Requirements**: FAUX-01, FAUX-02, FAUX-03

**Success Criteria** (what must be TRUE):
1. User can transcribe audio locally using faster-whisper with model auto-download
2. GPU acceleration works automatically (CUDA/MPS) with CPU fallback
3. Models download from HuggingFace on demand and cache locally
4. User can list, download, and delete cached models

**Plans**: 3 plans

Plans:
- [x] 07-01: Model Manager and Configuration (2026-03-25)
- [x] 07-02: FasterWhisperBackend Implementation (2026-03-25)
- [x] 07-03: Integration and Registry (2026-03-25)

---

### Phase 8: Backend Selection
**Goal**: Intelligent backend selection with auto and explicit policies
**Depends on**: Phase 5 (Backend Abstraction), Phase 6 (OpenAI Backend), Phase 7 (Faster-Whisper Backend)
**Requirements**: SEL-01, SEL-02, SEL-03

**Success Criteria** (what must be TRUE):
1. AUTO policy selects fastest available backend based on current conditions
2. PREFER_LOCAL uses cloud only if local backend unavailable
3. PREFER_CLOUD uses local only if API key missing
4. Explicit backend selection (CLI --backend, API backend parameter) overrides all policies

**Plans**: 2 plans

Plans:
- [x] 08-01: Backend availability checker (2026-03-25)
- [x] 08-02: Policy-based backend selector (2026-03-25)

---

### Phase 9: Pipeline & Core Output
**Goal**: Complete transcription workflow orchestration with basic output formats
**Depends on**: Phase 3 (Media Ingestion), Phase 4 (VAD Processing), Phase 8 (Backend Selection)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, OUT-01, OUT-02, ERR-03

**Success Criteria** (what must be TRUE):
1. User can run full pipeline: probe → extract → VAD → transcribe → output
2. Progress callbacks notify stage changes and percentage completion
3. Pipeline cleans up temp files on failure and preserves partial results when possible
4. User can get plain text output with timestamps per line
5. User can get JSON output with full metadata, segments, and configuration

**Plans**: 4 plans

Plans:
- [x] 09-01: Pipeline orchestrator implementation (2026-03-25)
- [x] 09-02: Progress callbacks and cancellation (2026-03-25)
- [x] 09-03: Plain text and JSON output serializers (2026-03-25)
- [x] 09-04: Pipeline error recovery and cleanup (2026-03-25)

---

### Phase 10: Complete Interface
**Goal**: Polished user experience across CLI, API, all output formats, and parallelism
**Depends on**: Phase 9 (Pipeline & Core Output)
**Requirements**: OUT-03, OUT-04, OUT-05, CLI-01, CLI-02, CLI-03, CLI-04, API-01, API-02, API-03, PARA-01, PARA-02

**Success Criteria** (what must be TRUE):
1. User can export transcriptions as SRT subtitles compatible with video players
2. User can export transcriptions as VTT format for web players
3. User can write output to file with directory creation and overwrite protection
4. User can run `audiocore transcribe <file>` with all configuration options
5. User can run `audiocore backends list` and `audiocore backends check` commands
6. User can run `audiocore models list`, `download`, `remove` for faster-whisper models
7. User can run `audiocore config show` with API keys redacted
8. Developer can import audiocore and call transcribe(path, options) from Python
9. All library errors are typed exceptions inheriting from AudioCoreError
10. Developer can use async_transcribe for non-blocking concurrent transcription
11. Pipeline processes VAD segments in parallel when enabled
12. CLI processes multiple files concurrently with --parallel flag

**Plans**: 5 plans

Plans:
- [ ] 10-01: SRT and VTT output serializers
- [ ] 10-02: File output with directory creation
- [ ] 10-03: CLI commands implementation
- [ ] 10-04: Public API with sync and async support
- [ ] 10-05: Parallel processing for segments and files

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-03-24 |
| 2. Configuration System | 3/3 | Complete | 2026-03-24 |
| 3. Media Ingestion | 3/3 | Complete | 2026-03-24 |
| 4. VAD Processing | 3/3 | Complete | 2026-03-25 |
| 5. Backend Abstraction | 2/2 | Complete | 2026-03-25 |
| 6. OpenAI Backend | 3/3 | Complete | 2026-03-25 |
| 7. Faster-Whisper Backend | 3/3 | Complete | 2026-03-25 |
| 8. Backend Selection | 2/2 | Complete | 2026-03-25 |
| 9. Pipeline & Core Output | 4/4 | Complete | 2026-03-25 |
| 10. Complete Interface | 1/5 | In Progress|  |

## Coverage Summary

| Phase | Requirements | Count |
|-------|-------------|-------|
| 1. Foundation | CORE-01, CORE-02, ERR-01, ERR-02 | 4 |
| 2. Configuration System | CONF-01, CONF-02, CONF-03 | 3 |
| 3. Media Ingestion | MEDIA-01, MEDIA-02, MEDIA-03 | 3 |
| 4. VAD Processing | VAD-01, VAD-02, VAD-03 | 3 |
| 5. Backend Abstraction | BACK-01, BACK-02 | 2 |
| 6. OpenAI Backend | OPEN-01, OPEN-02, OPEN-03 | 3 |
| 7. Faster-Whisper Backend | FAUX-01, FAUX-02, FAUX-03 | 3 |
| 8. Backend Selection | SEL-01, SEL-02, SEL-03 | 3 |
| 9. Pipeline & Core Output | PIPE-01, PIPE-02, PIPE-03, OUT-01, OUT-02, ERR-03 | 6 |
| 10. Complete Interface | OUT-03, OUT-04, OUT-05, CLI-01, CLI-02, CLI-03, CLI-04, API-01, API-02, API-03, PARA-01, PARA-02 | 12 |
| **Total** | | **39** |

**Coverage:** 39/39 v1 requirements mapped ✓
**No orphaned requirements.**

## Dependencies

```
Phase 1: Foundation
    ↓
Phase 2: Configuration ──────────────┐
    ↓                                 │
Phase 3: Media Ingestion              │
    ↓                                 │
Phase 4: VAD Processing ──────────────┤
                                      │
Phase 5: Backend Abstraction ←────────┘
    ↓
Phase 6: OpenAI Backend ────────────┐
    ↓                              │
Phase 7: Faster-Whisper Backend ──┬┘
    ↓                             │
Phase 8: Backend Selection ←──────┘
    ↓
Phase 9: Pipeline & Core Output
    ↓
Phase 10: Complete Interface
```

**Critical Path:** 1 → 2 → 3 → 4 → 8 → 9 → 10 (core dependency chain)

**Parallel Development Opportunities:**
- Phases 6 and 7 (OpenAI Backend, Faster-Whisper Backend) can be developed concurrently after Phase 5
- Phase 4 (VAD Processing) can be developed in parallel with Phases 5-7 after Media Ingestion

## Risk Mitigation

### Phase Risks

| Phase | Risk | Mitigation |
|-------|------|------------|
| 1. Foundation | Incomplete error coverage | Start with comprehensive error hierarchy before domain models |
| 2. Configuration | Priority chain bugs | Unit test priority resolution extensively |
| 3. Media Ingestion | ffmpeg compatibility | Test with real media files across formats early |
| 4. VAD Processing | Silero model compatibility | Verify torch hub access, provide model caching fallback |
| 5. Backend Abstraction | Over-engineered interface | Keep interface minimal, YAGNI until Phase 6 |
| 6. OpenAI Backend | API key handling | Redaction tests in Phase 1, apply here |
| 7. Faster-Whisper Backend | Model download failures | Implement retries, local cache fallback |
| 8. Backend Selection | Policy conflicts | Clear policy hierarchy documentation, unit tests |
| 9. Pipeline | Temp file cleanup | Context managers, finally blocks, explicit cleanup |
| 10. Complete Interface | Feature creep | Lock scope, defer enhancements to v2 |

### Technical Risks

1. **Silero VAD Memory Usage:** May spike on long files
   - Mitigation: Implement chunked processing, document memory requirements
   
2. **OpenAI API Rate Limits:** Could slow bulk processing
   - Mitigation: Built-in retry logic, rate limit config options
   
3. **Faster-Whisper GPU Compatibility:** CUDA/MPS variations
   - Mitigation: Extensive device detection, CPU fallback guaranteed
   
4. **Cross-Platform ffmpeg:** Binary location varies
   - Mitigation: Document system requirements, provide env var for path

## Effort Ranges

| Phase | Complexity | Estimated Effort | Notes |
|-------|-----------|------------------|-------|
| 1. Foundation | Medium | 2-3 days | Pydantic models, error hierarchy |
| 2. Configuration System | Low | 1-2 days | TOML parsing, priority chain |
| 3. Media Ingestion | Medium | 2-3 days | ffmpeg subprocess handling |
| 4. VAD Processing | Medium | 2-3 days | Silero integration, testing |
| 5. Backend Abstraction | Low | 1-2 days | Simple interface, registry |
| 6. OpenAI Backend | Medium | 2-3 days | API client, error handling |
| 7. Faster-Whisper Backend | Medium-High | 3-4 days | Model management, device handling |
| 8. Backend Selection | Low | 1-2 days | Policy logic, availability checks |
| 9. Pipeline & Core Output | High | 4-5 days | Orchestration, cleanup, outputs |
| 10. Complete Interface | High | 4-5 days | CLI, API, parallelism |

**Total Estimated Effort:** 22-32 development days (for experienced Python developer with Claude assistance)

This is a solo-developer estimate with Claude pair programming. Actual time will vary based on familiarity with the tech stack and testing rigor.