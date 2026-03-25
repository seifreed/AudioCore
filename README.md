<p align="center">
  <img src="https://img.shields.io/badge/AudioCore-Audio%2FVideo%20Transcription-blue?style=for-the-badge" alt="AudioCore">
</p>

<h1 align="center">AudioCore</h1>

<p align="center">
  <strong>Production-ready audio/video transcription with automatic backend selection</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/audiocore/"><img src="https://img.shields.io/pypi/v/audiocore?style=flat-square&logo=pypi&logoColor=white" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/audiocore/"><img src="https://img.shields.io/pypi/pyversions/audiocore?style=flat-square&logo=python&logoColor=white" alt="Python Versions"></a>
  <a href="https://github.com/seifreed/audiocore/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License"></a>
  <a href="https://github.com/seifreed/audiocore/actions"><img src="https://img.shields.io/github/actions/workflow/status/seifreed/audiocore/ci.yml?style=flat-square&logo=github&label=CI" alt="CI Status"></a>
  <img src="https://img.shields.io/badge/coverage-95%25-brightgreen?style=flat-square" alt="Coverage">
</p>

<p align="center">
  <a href="https://github.com/seifreed/audiocore/stargazers"><img src="https://img.shields.io/github/stars/seifreed/audiocore?style=flat-square" alt="GitHub Stars"></a>
  <a href="https://github.com/seifreed/audiocore/issues"><img src="https://img.shields.io/github/issues/seifreed/audiocore?style=flat-square" alt="GitHub Issues"></a>
  <a href="https://buymeacoffee.com/seifreed"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-yellow?style=flat-square&logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>
</p>

---

## Overview

**AudioCore** is a Python library for audio and video transcription with automatic backend selection. It seamlessly switches between OpenAI Whisper API (cloud) and faster-whisper (local) based on availability and user preferences, with built-in VAD segmentation, progress tracking, and comprehensive error handling.

### Key Features

| Feature | Description |
|---------|-------------|
| **Automatic Backend Selection** | Switches between OpenAI and faster-whisper automatically |
| **Voice Activity Detection** | Silero VAD for intelligent audio segmentation |
| **Multiple Output Formats** | Text, JSON, SRT, VTT subtitle formats |
| **Progress Tracking** | Stage-by-stage progress callbacks with cancellation support |
| **CLI & Library** | Use as command-line tool or Python library |
| **Async Support** | Non-blocking concurrent transcription |
| **Batch Processing** | Process multiple files concurrently |
| **Comprehensive Errors** | Typed exception hierarchy with actionable suggestions |

### Supported Backends

```
OpenAI Whisper API   Cloud transcription (requires API key)
Faster-Whisper       Local GPU/CPU transcription (no API needed)
Auto                 Automatically select best available
```

---

## Installation

### From PyPI (Recommended)

```bash
pip install audiocore
```

### From Source

```bash
git clone https://github.com/seifreed/audiocore.git
cd audiocore
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

### Optional Dependencies

```bash
# For faster-whisper (local transcription)
pip install audiocore[local]

# For development
pip install audiocore[dev]
```

---

## Quick Start

### Python Library

```python
from audiocore import transcribe, async_transcribe
from audiocore.types import BackendType, OutputFormat

# Synchronous transcription (auto-select backend)
result = transcribe("audio.mp3")
print(result.text)

# With options
result = transcribe(
    "video.mp4",
    backend=BackendType.OPENAI,
    output_format=OutputFormat.SRT
)

# Save to file
result.save("transcript.srt")
```

### Command Line Interface

```bash
# Basic transcription
audiocore transcribe audio.mp3

# With specific backend
audiocore transcribe video.mp4 --backend openai --format srt --output transcript.srt

# Batch processing
audiocore transcribe file1.mp3 file2.mp4 --parallel --max-workers 4

# Check backend availability
audiocore backends check
audiocore backends list

# Model management (faster-whisper)
audiocore models list
audiocore models download large-v3
audiocore models remove tiny
```

---

## Usage

### Command Line Interface

```bash
# Transcribe with defaults
audiocore transcribe podcast.mp3

# Specify backend and output format
audiocore transcribe meeting.mp4 --backend faster-whisper --format json

# Language specification
audiocore transcribe spanish.mp3 --language es

# Output to file
audiocore transcribe audio.mp3 --output transcript.txt

# Batch processing with concurrency
audiocore transcribe *.mp3 --parallel --max-workers 4

# Show configuration
audiocore config show
audiocore config path
```

### Available CLI Options

| Option | Description |
|--------|-------------|
| `--backend` | Backend to use: `openai`, `faster-whisper`, `auto` |
| `--language` | Language code (e.g., `en`, `es`, `fr`) |
| `--format` | Output format: `text`, `json`, `srt`, `vtt` |
| `--output`, `-o` | Output file path |
| `--parallel` | Enable parallel processing for multiple files |
| `--max-workers` | Maximum concurrent workers (default: 4) |
| `--model` | Model size: `tiny`, `base`, `small`, `medium`, `large-v3` |

### Python Library

#### Basic Usage

```python
from audiocore import transcribe
from audiocore.types import BackendType

# Simple transcription
result = transcribe("audio.mp3")
print(f"Duration: {result.duration_seconds}s")
print(f"Segments: {len(result.segments)}")
for seg in result.segments:
    print(f"[{seg.start_time:.2f}s - {seg.end_time:.2f}s] {seg.text}")
```

#### With Configuration

```python
from audiocore import transcribe, AppConfig
from audiocore.types import BackendType, OutputFormat

# Custom configuration
config = AppConfig(
    backend=BackendType.FASTER_WHISPER,
    language="en",
    output_format=OutputFormat.SRT,
)

result = transcribe("audio.mp3", config=config)
```

#### Progress Tracking

```python
from audiocore import Pipeline, PipelineStage

def on_progress(stage: PipelineStage, progress: float, message: str):
    print(f"[{stage.value}] {progress*100:.1f}% - {message}")

pipeline = Pipeline(progress_callback=on_progress)
result = pipeline.transcribe("audio.mp3")
```

#### Cancellation

```python
from audiocore import Pipeline, CancellationToken

token = CancellationToken()

# Cancel from another thread or after timeout
token.cancel()

result = pipeline.transcribe("audio.mp3", cancellation_token=token)
```

#### Async Transcription

```python
import asyncio
from audiocore import async_transcribe

async def main():
    # Single file
    result = await async_transcribe("audio.mp3")
    
    # Multiple files concurrently
    results = await async_transcribe(
        ["file1.mp3", "file2.mp3", "file3.mp3"],
        max_workers=4
    )
    
    for file_result in results:
        if file_result.success:
            print(f"{file_result.file}: {file_result.result.text}")
        else:
            print(f"{file_result.file}: Error - {file_result.error}")

asyncio.run(main())
```

#### Error Handling

```python
from audiocore import transcribe
from audiocore.errors import (
    AudioCoreError,
    MediaError,
    BackendUnavailableError,
    TranscriptionError,
)

try:
    result = transcribe("audio.mp3")
except MediaError as e:
    print(f"Media error: {e.message}")
    print(f"Suggestion: {e.suggestions[0]}")
except BackendUnavailableError as e:
    print(f"Backend unavailable: {e.message}")
except TranscriptionError as e:
    print(f"Transcription failed: {e.message}")
except AudioCoreError as e:
    print(f"AudioCore error: {e.message}")
```

---

## Examples

### Export to Subtitles

```python
from audiocore import transcribe
from audiocore.types import OutputFormat

# SRT for video players
result = transcribe("video.mp4", output_format=OutputFormat.SRT)
with open("video.srt", "w") as f:
    f.write(result.formatted_output)

# VTT for web players
result = transcribe("video.mp4", output_format=OutputFormat.VTT)
with open("video.vtt", "w") as f:
    f.write(result.formatted_output)
```

### Process Directory of Files

```python
from pathlib import Path
from audiocore import async_transcribe

async def process_directory(directory: Path):
    audio_files = list(directory.glob("*.mp3")) + list(directory.glob("*.mp4"))
    
    results = await async_transcribe(audio_files, max_workers=4)
    
    for file_result in results:
        if file_result.success:
            output_path = file_result.file.with_suffix(".txt")
            output_path.write_text(file_result.result.text)
            print(f"Processed: {file_result.file.name}")
        else:
            print(f"Failed: {file_result.file.name} - {file_result.error}")
```

### Use with OpenAI API

```python
from audiocore import transcribe
from audiocore.types import BackendType

# Requires OPENAI_API_KEY environment variable
result = transcribe("audio.mp3", backend=BackendType.OPENAI)
print(result.text)
```

### Use Local Transcription

```python
from audiocore import transcribe
from audiocore.types import BackendType

# No API key required
result = transcribe("audio.mp3", backend=BackendType.FASTER_WHISPER)
print(result.text)
```

---

## Configuration

### Environment Variables

```bash
export AUDIOCORE_OPENAI_API_KEY="sk-..."
export AUDIOCORE_FASTER_WHISPER_MODEL="large-v3"
export AUDIOCORE_FASTER_WHISPER_DEVICE="cuda"
export AUDIOCORE_VAD_MIN_SEGMENT_DURATION="0.5"
```

### Configuration File

Create `~/.config/audiocore/config.toml` or `./audiocore.toml`:

```toml
[audiocore]
backend = "auto"
language = "en"
output_format = "text"

[openai]
api_key = "sk-..."
timeout = 300
max_retries = 2

[faster_whisper]
model = "large-v3"
device = "cuda"
compute_type = "float16"

[vad]
min_segment_duration = 0.5
max_segment_duration = 30.0
speech_threshold = 0.5
```

### Priority Order

1. CLI arguments
2. Environment variables (`AUDIOCORE_*`)
3. Configuration file (`audiocore.toml`)
4. Default values

---

## Architecture

```
audiocore/
├── api/              # Public API (transcribe, async_transcribe)
├── backends/         # Backend implementations
│   ├── openai_backend.py
│   └── faster_whisper_backend.py
├── cli/              # Command-line interface
├── config/           # Configuration management
├── errors/           # Exception hierarchy
├── media/            # Audio/video processing
├── models/           # Data models
├── output/           # Output formatters (text, json, srt, vtt)
├── parallel/         # Concurrent processing
├── pipeline/         # Orchestration
├── types/            # Enums and constants
└── vad/              # Voice Activity Detection
```

---

## Requirements

- Python 3.14+
- **Required:** Pydantic v2, pydantic-settings
- **For OpenAI backend:** openai, httpx
- **For faster-whisper backend:** faster-whisper, torch, numpy
- **For media processing:** ffmpeg (system dependency)

See [pyproject.toml](pyproject.toml) for full dependency list.

---

## Development

### Setup Development Environment

```bash
git clone https://github.com/seifreed/audiocore.git
cd audiocore
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/audiocore --cov-report=html

# Run specific test file
pytest tests/unit/pipeline/test_orchestrator.py -v
```

### Code Quality

```bash
# Type checking
mypy src/audiocore

# Linting
ruff check src/audiocore

# Formatting
ruff format src/audiocore
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure all tests pass and code coverage remains above 95%.

---

## Roadmap

### Completed (v1.0)

- [x] Foundation (error hierarchy, types, models)
- [x] Configuration system (env, TOML, CLI)
- [x] Media ingestion (probe, extract)
- [x] VAD processing (Silero)
- [x] Backend abstraction
- [x] OpenAI Whisper API backend
- [x] Faster-Whisper local backend
- [x] Automatic backend selection
- [x] Pipeline orchestration
- [x] CLI and public API

### Future (v2.0)

- [ ] Real-time transcription
- [ ] Speaker diarization
- [ ] WebAssembly support
- [ ] Streaming API
- [ ] Custom VAD models

---

## Support the Project

If you find AudioCore useful, consider supporting its development:

<a href="https://buymeacoffee.com/seifreed" target="_blank">
  <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="50">
</a>

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Attribution Required:**
- Author: **Marc Rivero** | [@seifreed](https://github.com/seifreed)
- Repository: [github.com/seifreed/audiocore](https://github.com/seifreed/audiocore)

---

<p align="center">
  <sub>Made with dedication for the audio/video transcription community</sub>
</p>