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