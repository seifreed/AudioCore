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

| Backend | Type | Requirements |
|---------|------|--------------|
| **OpenAI Whisper API** | Cloud | API key (OPENAI_API_KEY) |
| **Faster-Whisper** | Local | GPU recommended, works on CPU |
| **Auto** | Automatic | Selects best available backend |

### Supported Models

| Backend | Available Models |
|---------|------------------|
| OpenAI | `whisper-1` (automatic) |
| Faster-Whisper | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo` |

### Supported Media Formats

AudioCore uses `ffmpeg` for media processing, supporting:

| Audio | Video |
|-------|-------|
| MP3, MP4, M4A, WAV, FLAC | MP4, MKV, AVI, MOV, WebM |
| OGG, OPUS, AAC, WMA | And most other video formats |

---

## Installation

### Prerequisites

1. **Python 3.11+**
2. **ffmpeg** (for media processing)
   ```bash
   # macOS
   brew install ffmpeg
   
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # Windows
   winget install ffmpeg
   ```

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
# For CUDA support (faster local transcription)
pip install audiocore[cuda]

# For development
pip install audiocore[dev]
```

---

## Quick Start

### Python Library

```python
from audiocore import transcribe
from audiocore.types import BackendType, OutputFormat

# Simple transcription (auto-select backend)
result = transcribe("audio.mp3")
print(result.formatted_output)

# With specific options
result = transcribe(
    "video.mp4",
    backend=BackendType.OPENAI,
    language="es",
    output_format=OutputFormat.SRT
)

# Access segments
for segment in result.segments:
    print(f"[{segment.start_time:.2f}s - {segment.end_time:.2f}s] {segment.text}")

# Metadata
print(f"Processing time: {result.processing_time_seconds:.2f}s")
print(f"Backend used: {result.backend_used}")
```

### Command Line Interface

```bash
# Basic transcription
audiocore transcribe audio.mp3

# Spanish with SRT output
audiocore transcribe video.mp4 --language es --format srt --output transcript.srt

# Use local faster-whisper
audiocore transcribe podcast.mp3 --backend faster-whisper --model small

# Batch processing
audiocore transcribe *.mp3 --parallel --max-workers 4 --output-dir transcripts/

# Check backend availability
audiocore backends check
```

---

## CLI Reference

### Transcribe Command

```bash
audiocore transcribe [OPTIONS] FILE [FILE ...]
```

| Option | Description |
|--------|-------------|
| `--backend`, `-b` | Backend: `openai`, `faster_whisper`, `auto` (default: auto) |
| `--language`, `-l` | Language code: `en`, `es`, `fr`, `de`, etc. |
| `--format`, `-f` | Output format: `text`, `json`, `srt`, `vtt` |
| `--output`, `-o` | Output file path |
| `--model`, `-m` | Model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `--parallel` | Enable parallel processing for multiple files |
| `--max-workers` | Max concurrent workers (default: 4) |
| `--strict-vad` | Fail if VAD processing fails (default: fallback to whole-file) |

### Backend Commands

```bash
# Check which backends are available
audiocore backends check

# List backend status
audiocore backends list
```

### Config Commands

```bash
# Show current configuration
audiocore config show

# Show config file location
audiocore config path
```

---

## Python API Reference

### Main Functions

#### `transcribe()`

```python
from audiocore import transcribe
from audiocore.types import BackendType, OutputFormat, ModelSize
from audiocore.models import TranscriptionOptions

# Simple usage
result = transcribe("audio.mp3")

# With TranscriptionOptions
options = TranscriptionOptions(
    backend=BackendType.FASTER_WHISPER,
    model_size=ModelSize.SMALL,
    language="es",
    output_format=OutputFormat.JSON,
    strict_vad=True,  # Fail on VAD errors instead of fallback
)
result = transcribe("audio.mp3", options=options)

# Return type: TranscriptionResult
# - result.segments: List[Segment]
# - result.formatted_output: str (formatted based on output_format)
# - result.processing_time_seconds: float
# - result.backend_used: BackendType
# - result.media_info: MediaInfo
```

#### `async_transcribe()`

```python
import asyncio
from audiocore import async_transcribe

async def main():
    # Single file
    result = await async_transcribe("audio.mp3")
    
    # Multiple files
    results = await async_transcribe(
        ["file1.mp3", "file2.mp4"],
        max_workers=4
    )
    
    for file_result in results:
        if file_result.success:
            print(f"{file_result.path}: OK")
        else:
            print(f"{file_result.path}: Error - {file_result.error}")

asyncio.run(main())
```

### Pipeline Class

```python
from audiocore import Pipeline
from audiocore.pipeline.progress import PipelineStage

def on_progress(stage: PipelineStage, progress: float, message: str):
    print(f"[{stage.value}] {progress*100:.1f}% - {message}")

pipeline = Pipeline(progress_callback=on_progress)
result = pipeline.transcribe("audio.mp3")
```

### Cancellation

```python
from audiocore import Pipeline, CancellationToken
import threading
import time

token = CancellationToken()

def cancel_after_timeout():
    time.sleep(30)  # Cancel after 30 seconds
    token.cancel()

threading.Thread(target=cancel_after_timeout, daemon=True).start()

try:
    result = pipeline.transcribe("video.mp4", cancellation_token=token)
except CancelledError:
    print("Transcription was cancelled")
```

---

## Configuration

### Environment Variables

```bash
# OpenAI API
export AUDIOCORE_OPENAI_API_KEY="sk-..."
export AUDIOCORE_OPENAI_TIMEOUT="300"
export AUDIOCORE_OPENAI_MAX_RETRIES="2"

# Faster-Whisper
export AUDIOCORE_FASTER_WHISPER_MODEL="small"
export AUDIOCORE_FASTER_WHISPER_DEVICE="cuda"  # cuda, cpu, or auto
export AUDIOCORE_FASTER_WHISPER_COMPUTE_TYPE="float16"

# VAD settings
export AUDIOCORE_VAD_MIN_SEGMENT_DURATION="0.5"
export AUDIOCORE_VAD_MAX_SEGMENT_DURATION="30.0"
export AUDIOCORE_VAD_SPEECH_THRESHOLD="0.5"

# General settings
export AUDIOCORE_BACKEND="auto"
export AUDIOCORE_LANGUAGE="es"
export AUDIOCORE_MODEL="base"
export AUDIOCORE_OUTPUT_FORMAT="text"
export AUDIOCORE_STRICT_VAD="false"
```

### Configuration File

Create `~/.config/audiocore/config.toml` or `./audiocore.toml`:

```toml
[audiocore]
backend = "auto"
language = "en"
model = "base"
output_format = "text"
strict_vad = false
backend_preference = "auto"  # auto, prefer_local, prefer_cloud

[openai]
api_key = "sk-..."
timeout = 300
max_retries = 2

[faster_whisper]
model = "small"
device = "cuda"
compute_type = "float16"
beam_size = 5
temperature = 0.0

[vad]
min_segment_duration = 0.5
max_segment_duration = 30.0
speech_threshold = 0.5
min_silence_duration_ms = 500
```

### Priority Order

1. CLI arguments (highest priority)
2. Environment variables (`AUDIOCORE_*`)
3. Configuration file (`audiocore.toml`)
4. Default values (lowest priority)

---

## Backend Details

### OpenAI Whisper API

**Requirements:**
- OpenAI API key (`OPENAI_API_KEY` environment variable)
- Internet connection
- Credits in your OpenAI account

**Configuration:**

```toml
[openai]
api_key = "sk-..."
base_url = "https://api.openai.com/v1"  # Optional: for proxies
timeout = 300
max_retries = 2
max_upload_size_mb = 25
chunk_target_size_mb = 24
chunk_min_duration_seconds = 30
chunk_prompt_chars = 1000
```

AudioCore automatically detects OpenAI uploads larger than `max_upload_size_mb`,
splits them with ffmpeg into chunks below `chunk_target_size_mb`, transcribes
each chunk, and recombines timestamps in the final result.

**Advantages:**
- High quality transcription
- No local GPU needed
- Fast API response

**Limitations:**
- Requires API key
- Costs per minute of audio
- Requires internet connection
- Large files require ffmpeg/ffprobe for automatic chunking

### Faster-Whisper (Local)

**Requirements:**
- `faster-whisper` package (installed by default)
- Optional: CUDA GPU for faster inference
- Model downloaded on first use (cached locally)

**Configuration:**

```toml
[faster_whisper]
model = "small"           # tiny, base, small, medium, large-v3
device = "auto"            # auto, cuda, cpu
compute_type = "float16"   # float16, float32, int8
beam_size = 5
temperature = 0.0
```

**Model Sizes:**

| Model | VRAM | Speed | Quality |
|-------|------|-------|---------|
| `tiny` | ~1GB | Fastest | Basic |
| `base` | ~1GB | Very Fast | Good |
| `small` | ~2GB | Fast | Better |
| `medium` | ~5GB | Medium | Very Good |
| `large-v3` | ~10GB | Slow | Best |

**Advantages:**
- Free (no API costs)
- Works offline
- Privacy (data doesn't leave your machine)
- GPU acceleration support

**Note on Device Selection:**
- `cuda`: Use NVIDIA GPU
- `cpu`: Use CPU (slower but works everywhere)
- `auto`: Automatically detect best available (CUDA > CPU)
- **MPS (Apple Silicon)**: Currently not supported by CTranslate2, falls back to CPU

---

## VAD (Voice Activity Detection)

AudioCore uses Silero VAD to segment audio into speech chunks before transcription:

```python
from audiocore.vad import VADConfig

config = VADConfig(
    min_segment_duration=0.5,      # Minimum segment length (seconds)
    max_segment_duration=30.0,      # Maximum segment length (seconds)
    speech_threshold=0.5,           # Speech probability threshold (0-1)
    min_silence_duration_ms=500,    # Minimum silence to split (ms)
)

result = transcribe("audio.mp3", vad_config=config)
```

**VAD Behavior:**
- If VAD fails and `strict_vad=False` (default): Falls back to whole-file transcription
- If VAD fails and `strict_vad=True`: Raises `VADError`

---

## Error Handling

```python
from audiocore import transcribe
from audiocore.errors import (
    AudioCoreError,
    MediaError,
    BackendUnavailableError,
    TranscriptionError,
    InvalidInputError,
    VADError,
    RateLimitError,
    AuthenticationError,
)

try:
    result = transcribe("audio.mp3")
except InvalidInputError as e:
    print(f"Invalid input: {e.message}")
    print(f"Suggestions: {e.suggestions}")
except MediaError as e:
    print(f"Media processing error: {e.message}")
except BackendUnavailableError as e:
    print(f"No backend available: {e.message}")
    print(f"Available backends: {e.context.get('available_backends')}")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.context.get('retry_after')}s")
except AuthenticationError as e:
    print(f"Authentication failed: {e.message}")
except VADError as e:
    print(f"VAD processing failed: {e.message}")
except TranscriptionError as e:
    print(f"Transcription failed: {e.message}")
except AudioCoreError as e:
    print(f"AudioCore error: {e.message}")
```

**Error Types:**

| Error | Description |
|-------|-------------|
| `InvalidInputError` | Invalid file path or format |
| `MediaError` | FFmpeg processing error |
| `BackendUnavailableError` | No backend available |
| `AuthenticationError` | API authentication failed |
| `RateLimitError` | API rate limit exceeded |
| `VADError` | VAD processing failed |
| `TranscriptionError` | Transcription failed |
| `PipelineError` | Pipeline processing error |

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

# JSON with metadata
result = transcribe("video.mp4", output_format=OutputFormat.JSON)
with open("video.json", "w") as f:
    f.write(result.formatted_output)
```

### Process Multiple Files

```python
import asyncio
from pathlib import Path
from audiocore import async_transcribe
from audiocore.types import BackendType

async def process_directory(directory: Path):
    audio_files = list(directory.glob("*.mp3")) + list(directory.glob("*.mp4"))
    
    results = await async_transcribe(
        audio_files,
        backend=BackendType.FASTER_WHISPER,
        max_workers=4
    )
    
    for file_result in results:
        if file_result.success:
            output_path = file_result.path.with_suffix(".txt")
            output_path.write_text(file_result.result.formatted_output)
            print(f"✓ {file_result.path.name}")
        else:
            print(f"✗ {file_result.path.name}: {file_result.error}")

asyncio.run(process_directory(Path("videos/")))
```

### Progress Tracking

```python
from audiocore import Pipeline
from audiocore.pipeline.progress import PipelineStage

def on_progress(stage: PipelineStage, progress: float, message: str):
    stages = {
        PipelineStage.PROBING: "📊",
        PipelineStage.EXTRACTING: "🎵",
        PipelineStage.VAD: "🗣️",
        PipelineStage.TRANSCRIBING: "✍️",
        PipelineStage.FORMATTING: "📝",
        PipelineStage.COMPLETE: "✅",
    }
    emoji = stages.get(stage, "⏳")
    print(f"\r{emoji} [{stage.value}] {progress*100:.0f}% - {message}", end="", flush=True)

pipeline = Pipeline(progress_callback=on_progress)
result = pipeline.transcribe("video.mp4")
print()  # New line after progress
```

### Custom VAD Configuration

```python
from audiocore import transcribe
from audiocore.vad import VADConfig
from audiocore.types import BackendType

# More aggressive VAD (faster processing, may miss speech)
fast_vad = VADConfig(
    speech_threshold=0.7,
    min_segment_duration=0.3,
    max_segment_duration=60.0,
)

# More sensitive VAD (slower processing, catches more speech)
sensitive_vad = VADConfig(
    speech_threshold=0.3,
    min_segment_duration=0.5,
    min_silence_duration_ms=200,
)

result = transcribe("audio.mp3", vad_config=fast_vad)
```

---

## Architecture

```
audiocore/
├── api/                    # Public API
│   ├── transcribe.py       # Main transcribe functions
│   └── __init__.py         # Public exports
├── backends/               # Backend implementations
│   ├── base.py             # Abstract backend interface
│   ├── openai_backend.py   # OpenAI Whisper API
│   ├── faster_whisper_backend.py  # Local faster-whisper
│   ├── registry.py         # Backend registration
│   ├── availability.py     # Backend availability checking
│   └── selector.py         # Automatic backend selection
├── cli/                    # Command-line interface
│   ├── main.py             # Typer app
│   ├── transcribe.py       # Transcribe command
│   └── config_cmd.py       # Config commands
├── config/                 # Configuration management
│   ├── settings.py         # AppConfig (pydantic-settings)
│   ├── openai_config.py    # OpenAI-specific config
│   ├── faster_whisper_config.py  # Faster-whisper config
│   └── merger.py           # Config priority handling
├── errors/                 # Exception hierarchy
│   ├── base.py             # AudioCoreError base
│   ├── input.py            # InvalidInputError, MediaFormatError
│   ├── media.py            # MediaError
│   ├── backend.py          # BackendUnavailableError
│   ├── transcription.py    # TranscriptionError
│   └── vad.py              # VADError
├── media/                  # Media processing
│   ├── probe.py            # FFprobe wrapper
│   └── extractor.py        # Audio extraction (ffmpeg)
├── models/                 # Data models
│   ├── segment.py          # Segment model
│   ├── media.py            # MediaInfo model
│   └── transcription.py    # TranscriptionResult, TranscriptionOptions
├── output/                 # Output formatters
│   ├── text.py             # Plain text
│   ├── json.py             # JSON format
│   ├── srt.py              # SRT subtitles
│   └── vtt.py              # VTT subtitles
├── parallel/               # Concurrent processing
│   └── files.py            # transcribe_files_concurrent()
├── pipeline/               # Orchestration
│   ├── orchestrator.py     # Main pipeline
│   ├── progress.py         # Progress tracking
│   ├── errors.py           # Pipeline-specific errors
│   └── cancellation.py      # CancellationToken
├── types/                  # Enums and constants
│   └── enums.py            # BackendType, OutputFormat, etc.
├── vad/                    # Voice Activity Detection
│   ├── silero.py           # Silero VAD implementation
│   ├── segments.py         # Segment merging/padding
│   └── config.py           # VADConfig
└── __init__.py             # Package exports
```

---

## Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | ≥3.11 | Runtime |
| ffmpeg | System | Media processing |
| Pydantic | ≥2.0 | Data validation |
| openai | ≥1.0 | OpenAI API client |
| faster-whisper | ≥1.0 | Local transcription |
| torch | ≥2.0 | Silero VAD |
| torchaudio | ≥2.0 | Audio processing |
| huggingface-hub | ≥0.20 | Model downloads |
| typer | ≥0.9 | CLI framework |
| rich | ≥13.0 | CLI formatting |

---

## Development

### Setup

```bash
git clone https://github.com/seifreed/audiocore.git
cd audiocore
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/audiocore --cov-report=html

# Specific test file
pytest tests/unit/pipeline/test_orchestrator.py -v

# Integration tests
pytest tests/integration/ -v
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

## Troubleshooting

### "ffmpeg not found"

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

### "CUDA not available"

The code automatically falls back to CPU. For CUDA support:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### "MPS (Apple Silicon) not working"

faster-whisper uses CTranslate2 which doesn't support MPS. The code automatically falls back to CPU.

### "Model download is slow"

Models are cached after first download. To pre-download:
```python
from audiocore.backends.faster_whisper_backend import FasterWhisperBackend
backend = FasterWhisperBackend()
backend._load_model()  # Downloads and caches model
```

### "VAD processing failed"

With `strict_vad=False` (default), the system falls back to whole-file transcription. Set `strict_vad=True` to raise errors instead.

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
- [x] Multiple output formats (text, JSON, SRT, VTT)
- [x] Progress tracking
- [x] Cancellation support
- [x] Concurrent batch processing
- [x] Comprehensive error handling

### Future (v2.0)

- [ ] Real-time transcription
- [ ] Speaker diarization
- [ ] WebAssembly support
- [ ] Streaming API
- [ ] Custom VAD models
- [x] Word-level timestamps
- [x] Translation API

#### Word-level timestamps

Pass `word_timestamps=True` (or `--word-timestamps` on the CLI) to attach
per-word timing to every segment. Works with both backends — faster-whisper
emits native word timestamps with confidence; the OpenAI backend requests
`timestamp_granularities`. Words are included in JSON output.

```python
from audiocore import transcribe
from audiocore.models import TranscriptionOptions
from audiocore.types import OutputFormat

result = transcribe(
    "audio.mp3",
    options=TranscriptionOptions(word_timestamps=True, output_format=OutputFormat.JSON),
)
for segment in result.segments:
    for word in segment.words or []:
        print(f"[{word.start_time:.2f}-{word.end_time:.2f}] {word.word}")
```

```bash
audiocore transcribe audio.mp3 --word-timestamps --format json
```

#### Translation API

Pass `task=TranscriptionTask.TRANSLATE` (or `--translate` on the CLI) to
translate speech into English. faster-whisper uses its `translate` task; the
OpenAI backend routes to the dedicated translations endpoint. (Whisper's
translate task always targets English regardless of the source language.)

```python
from audiocore import transcribe
from audiocore.models import TranscriptionOptions
from audiocore.types import TranscriptionTask

result = transcribe(
    "entrevista_es.mp3",
    options=TranscriptionOptions(task=TranscriptionTask.TRANSLATE),
)
print(result.formatted_output)  # English translation
```

```bash
audiocore transcribe entrevista_es.mp3 --translate
```

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
