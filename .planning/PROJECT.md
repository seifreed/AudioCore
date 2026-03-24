# PROJECT.md

## Project Identity

**Name:** AudioCore  
**Type:** Python Library + CLI  
**Version Target:** 1.0.0

## Core Value

AudioCore is a Python 3.14 audio/video transcription engine that provides reliable, flexible transcription through dual backend support (OpenAI Whisper API and faster-whisper). It bridges the gap between cloud-based and local transcription by offering automatic backend selection with configurable policies, while handling the complexity of audio extraction, voice activity detection, and output formatting.

**Why this project exists:**
- Developers need transcription without managing audio preprocessing
- Users want choice between cloud (quality/speed) and local (privacy/cost)
- Existing solutions are either/or, not both with smart selection
- VAD-based segmentation improves accuracy and reduces costs

## Primary Users

1. **CLI Users:** Content creators, journalists, researchers who want quick transcription from command line
2. **Library Users:** Developers integrating transcription into applications (podcasts, video platforms, meeting tools)

## Constraints

### Technical Constraints
- Python 3.14 minimum (modern type hints, performance optimizations)
- System ffmpeg binary required (not bundled)
- Silero VAD model weights (~5MB) downloaded on first use
- Pydantic v2 for all models and validation

### Design Constraints
- Must work as both CLI tool and importable library
- Must never log or leak API keys
- Must maintain temporal order of segments (no sorting after the fact)
- Must handle all errors through typed exception hierarchy
- Auto-selection must be deterministic and configurable

### Quality Constraints
- Full type coverage (no Any types in public API)
- Comprehensive error messages with actionable guidance
- CLI help must be self-documenting
- Library must be usable without reading source code

## Non-Goals

1. **Real-time streaming transcription** - batch processing only
2. **Speaker diarization** - single speaker model
3. **Language detection** - language must be specified or default assumed
4. **Model fine-tuning** - use pre-trained models only
5. **Audio editing/manipulation** - extraction only for transcription purposes
6. **Cloud storage integration** - local file paths only

## Success Metrics

1. **Functional:** 100% of planned output formats working
2. **Performance:** Auto-selection chooses correct backend within policy constraints
3. **Usability:** New user can transcribe first file within 60 seconds of install
4. **Reliability:** Graceful error handling with typed exceptions for all failure modes
5. **Adoption:** Library API feels Pythonic and intuitive to developers

## Architecture Principles

1. **Separation of concerns:** Each component has single responsibility
2. **Dependency injection:** Backends, VAD, and output formats are pluggable
3. **Fail fast:** Validate inputs before heavy processing
4. **Graceful degradation:** Partial results better than nothing when recoverable
5. **Thread-safe:** Library calls must be safe for concurrent use

## Key Design Decisions

1. **Pydantic for all models:** Validation, serialization, and IDE support built-in
2. **Typer for CLI:** Modern, type-safe CLI with minimal boilerplate
3. **Abstract backend interface:** Swappable backends with consistent behavior
4. **VAD-first segmentation:** Always segment before sending to transcription backend
5. **Configuration priority:** CLI args > env vars > TOML file > defaults

## Timeline Philosophy

This is a solo-developer project with Claude assistance. Phases represent logical delivery boundaries, not time boxes. Each phase produces a verifiable increment of functionality.

## Related Documents

- `.planning/REQUIREMENTS.md` - Detailed functional requirements
- `.planning/ROADMAP.md` - Phase structure and success criteria
- `.planning/STATE.md` - Current position and progress