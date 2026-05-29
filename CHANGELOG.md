# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Word-level timestamps (`TranscriptionOptions.word_timestamps`, `--word-timestamps`).
  Adds a `Word` model and a `Segment.words` field populated by both backends
  (faster-whisper native word timestamps with confidence; OpenAI
  `timestamp_granularities`). Words appear in JSON output.
- Translation task (`TranscriptionOptions.task`, `TranscriptionTask`, `--translate`).
  Translates speech to English via faster-whisper's `translate` task or the
  OpenAI translations endpoint.
- Custom VAD models. Adds a `VADModel` protocol so any detector can drive the
  speech-detection stage (`transcribe(..., vad_model=...)`, `Pipeline(vad_model=...)`),
  plus `VADConfig.model_path` to load a custom Silero-format TorchScript model.
- Streaming API. Adds `stream_transcribe()` and `Pipeline.stream_transcribe()`
  yielding `Segment` objects incrementally, plus a `TranscriptionBackend.transcribe_stream`
  hook (faster-whisper streams lazily from its decode generator).
- Real-time transcription (`audiocore.realtime`). Adds an `AudioSource` protocol,
  an optional `sounddevice`-backed `MicrophoneSource`, an energy-based
  `UtteranceSegmenter`, and `RealtimeTranscriber` / `transcribe_realtime` that
  stream a live source into transcribed segments. New optional extra: `realtime`.
- Speaker diarization (`audiocore.diarization`). Adds a `Diarizer` protocol,
  `SpeakerTurn`, `assign_speakers`, and an optional `PyannoteDiarizer`. Wired
  through `transcribe(..., diarizer=...)` / `Pipeline(diarizer=...)`; labels land
  on a new `Segment.speaker` field. New optional extra: `diarization`. Adds a
  `PipelineStage.DIARIZING` stage.
- WebAssembly support (`audiocore.wasm`). A Pyodide-safe surface
  (`format_transcript`, `segments_from_data`, `is_wasm`) that renders
  text/JSON/SRT/VTT from segment data without importing torch, ctranslate2,
  ffmpeg, openai, or any backend.
- SBOM integration via [sbom-tools](https://github.com/sbom-tool/sbom-tools).
  A reproducible `sbom/generate_sbom.py` pipeline emits an enriched CycloneDX
  SBOM of the runtime dependency closure (`sbom/audiocore.cdx.json`) that scores
  **Grade A** (91.5/100 standard, 92.2 minimal) with Completeness, Identifiers,
  and Integrity at 100/100 and NTIA-minimum-elements compliance. Adds a
  `Makefile` (`make sbom`/`sbom-score`/`sbom-validate`) and a `sbom.yml` CI
  workflow that gates the rating at Grade A.

### Changed
- `Pipeline` and `transcribe` are now imported lazily from `audiocore.pipeline`
  (via module `__getattr__`), so `import audiocore` no longer eagerly loads the
  backend layer. The public import paths are unchanged.

## [1.0.0] - 2025-03-27

### Added
- Initial release of AudioCore
- Dual backend support: OpenAI Whisper API and faster-whisper (local)
- Voice Activity Detection (VAD) with Silero
- Multiple output formats: text, JSON, SRT, VTT
- CLI and Python API interfaces
- Async transcription support
- Batch processing with parallel execution
- Progress tracking with cancellation support
- Comprehensive error handling with actionable suggestions
- Automatic backend selection with preference policies
- Model management CLI commands
- Configuration via environment variables and TOML files

### Security
- Input validation for executable paths to prevent command injection
- HuggingFace Hub downloads with revision pinning
- Secure subprocess execution with input sanitization
- Thread-safe singleton patterns for backend registry and VAD
- Atomic counter operations for parallel processing

### Supported Platforms
- Linux (x64, ARM64)
- macOS (x64, ARM64/M-series)
- Windows (x64)

### Dependencies
- Python >=3.14
- Pydantic >=2.0.0
- torch >=2.0.0
- faster-whisper >=1.0.0
- openai >=1.0.0
- huggingface-hub >=0.20.0