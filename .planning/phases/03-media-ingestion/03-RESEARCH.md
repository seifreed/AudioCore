# Research: Phase 3 - Media Ingestion

## Objective
Answer: "What do I need to know to PLAN this phase well?"

---

## 1. Domain Analysis

### ffprobe for Media Probing

**Purpose:** Extract metadata from media files without decoding the full content.

**Key capabilities:**
- Format detection (container format)
- Stream information (codec, sample rate, channels, bit rate)
- Duration extraction
- Resolution (for video)

**Command patterns:**
```bash
# JSON output (recommended for parsing)
ffprobe -v quiet -print_format json -show_format -show_streams <file>

# Specific stream info
ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of default=noprint_wrappers=1:nokey=1 <file>

# Duration only
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <file>
```

**Output parsing:**
- JSON output is most reliable for parsing
- `-v quiet` suppresses logs (use `-v error` to capture stderr for errors)
- Duration may be in `format.duration` or calculated from streams

**Error handling:**
- Exit code 0 ≠ valid file (corrupted files may still probe)
- Check stderr for warning messages
- Invalid codec/container → exit code varies
- Missing file → exit code varies by version

### ffmpeg for Audio Extraction

**Purpose:** Convert any media to normalized 16kHz mono WAV.

**Key requirements from REQUIREMENTS.md:**
- Convert to 16kHz mono WAV
- Support seeking (start position)
- Support duration limit
- Create temporary output file
- Progress callback support

**Command pattern for extraction:**
```bash
# Basic extraction to 16kHz mono WAV
ffmpeg -i <input> -ar 16000 -ac 1 -c:a pcm_s16le output.wav

# With seeking (fast: before -i)
ffmpeg -ss 00:01:30 -i <input> -ar 16000 -ac 1 -c:a pcm_s16le output.wav

# With duration limit
ffmpeg -ss 00:01:30 -i <input> -t 00:00:30 -ar 16000 -ac 1 -c:a pcm_s16le output.wav

# Progress output (for callbacks)
ffmpeg -progress pipe:1 -i <input> -ar 16000 -ac 1 -c:a pcm_s16le output.wav
```

**Progress callback implementation:**
```python
# Use -progress pipe:1 or -stats
# Parse stderr for progress info
# Calculate percentage from duration extracted
```

**Audio quality for transcription:**
- 16kHz sample rate (Whisper optimal)
- Mono channel
- PCM signed 16-bit little-endian (lossless)
- No compression artifacts

---

## 2. Implementation Strategy

### Module Structure

**Proposed structure:**
```
src/audiocore/media/
    __init__.py           # Public API: probe() and extract()
    probe.py              # ffprobe wrapper for metadata extraction
    extractor.py          # ffmpeg wrapper for audio extraction
    formats.py            # Format validation and support list
    exceptions.py         # Media-specific exceptions (if needed)
```

**Public API functions:**
```python
def probe(file_path: Path) -> MediaInfo:
    """Probe media file and return metadata."""
    ...

def extract_audio(
    file_path: Path,
    output_path: Path | None = None,
    start_time: float | None = None,
    duration: float | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Path:
    """Extract and normalize audio to 16kHz mono WAV."""
    ...

def is_format_supported(file_path: Path) -> bool:
    """Check if file format is supported."""
    ...
```

### Plan Breakdown

**Plan 03-01: Media probing with ffprobe**
- Implement `probe()` function using subprocess
- Parse ffprobe JSON output
- Map to existing MediaInfo model
- Handle ffprobe errors and edge cases
- Add MediaError for general probe failures (extends ProcessingError)

**Plan 03-02: Audio extraction with ffmpeg normalization**
- Implement `extract_audio()` function using subprocess
- Support seeking and duration parameters
- Generate temp WAV files
- Implement progress callback via stderr parsing
- Handle ffmpeg errors and convert to typed exceptions

**Plan 03-03: Format validation and error handling**
- Define SUPPORTED_FORMATS constants
- Implement format detection from file extension and ffprobe
- MediaFormatError for unsupported formats with guidance
- Integration tests with real media files

---

## 3. Technical Decisions

### Decision 1: subprocess.run vs asyncio subprocess

**Recommendation:** Use `subprocess.run()` (synchronous)

**Rationale:**
- Simpler implementation, easier error handling
- Progress callback can be implemented with stderr pipe reading
- Phase implementation is simpler
- Async subprocess adds complexity without clear benefit for Phase 3
- Async API is planned for Phase 10 (future enhancement)

**Implementation pattern:**
```python
result = subprocess.run(
    ["ffprobe", ...],
    capture_output=True,
    text=True,
    timeout=30,
)
```

### Decision 2: ffprobe output format

**Recommendation:** Use JSON output (`-print_format json`)

**Rationale:**
- Reliable parsing with `json.loads()`
- No string parsing edge cases
- ffprobe JSON is documented and stable
- Easy to extract nested values

### Decision 3: Temp file handling

**Recommendation:** Use `tempfile.NamedTemporaryFile()` with explicit cleanup

**Rationale:**
- Context manager for automatic cleanup
- Predictable file naming
- Security (temp directory permissions)
- Phase 9 Pipeline will orchestrate cleanup

**Pattern:**
```python
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
    temp_path = Path(tmp.name)
try:
    # ffmpeg writes to temp_path
    yield temp_path
finally:
    temp_path.unlink(missing_ok=True)
```

### Decision 4: ffmpeg path configuration

**Recommendation:** Add `ffprobe_path` and `ffmpeg_path` to AppConfig

**Rationale:**
- Users may have ffmpeg in non-standard locations
- Windows users often have ffmpeg in custom paths
- Cross-platform compatibility
- Matches existing AppConfig pattern from Phase 2

**Config additions:**
```python
class AppConfig(BaseSettings):
    # ... existing fields ...
    ffprobe_path: str = Field(default="ffprobe", description="Path to ffprobe binary")
    ffmpeg_path: str = Field(default="ffmpeg", description="Path to ffmpeg binary")
```

### Decision 5: Format support list

**Recommendation:** Define as module-level constant, validate via ffprobe

**Rationale:**
- Explicit list enables clear error messages
- ffprobe validation detects actual capabilities
- Some formats may work even if not in list (codecs matter more)
- Extension-based pre-filter for faster errors

**Implementation:**
```python
SUPPORTED_AUDIO_FORMATS = {"mp3", "wav", "m4a", "flac", "ogg", "aac"}
SUPPORTED_VIDEO_FORMATS = {"mp4", "mkv", "avi", "mov", "webm"}
SUPPORTED_FORMATS = SUPPORTED_AUDIO_FORMATS | SUPPORTED_VIDEO_FORMATS
```

---

## 4. Standard Patterns

### ffprobe subprocess pattern

```python
import json
import subprocess
from pathlib import Path

def probe_file(file_path: Path, ffprobe_path: str = "ffprobe") -> dict:
    """Probe media file using ffprobe."""
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,  # 30 second timeout for probing
    )
    
    if result.returncode != 0:
        raise MediaFormatError(
            f"ffprobe failed for {file_path}",
            context={"file_path": str(file_path), "stderr": result.stderr},
            cause=subprocess.CalledProcessError(result.returncode, cmd),
        )
    
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise MediaFormatError(
            f"Invalid ffprobe output for {file_path}",
            context={"file_path": str(file_path)},
            cause=e,
        )
```

### ffmpeg subprocess pattern

```python
def extract_audio(
    input_path: Path,
    output_path: Path,
    sample_rate: int = 16000,
    channels: int = 1,
    start_time: float | None = None,
    duration: float | None = None,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """Extract audio from media file."""
    cmd = [ffmpeg_path, "-y"]  # -y to overwrite
    
    if start_time is not None:
        cmd.extend(["-ss", str(start_time)])
    
    cmd.extend(["-i", str(input_path)])
    
    if duration is not None:
        cmd.extend(["-t", str(duration)])
    
    cmd.extend([
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "pcm_s16le",
        str(output_path),
    ])
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,  # 1 hour max
    )
    
    if result.returncode != 0:
        raise MediaFormatError(
            f"ffmpeg extraction failed for {input_path}",
            context={"file_path": str(input_path), "stderr": result.stderr},
            cause=subprocess.CalledProcessError(result.returncode, cmd),
        )
    
    return output_path
```

### Progress callback pattern

```python
def extract_with_progress(
    input_path: Path,
    output_path: Path,
    duration: float,  # Total duration from probe
    progress_callback: Callable[[float], None],
    **kwargs,
) -> Path:
    """Extract audio with progress updates."""
    cmd = [
        "ffmpeg",
        "-progress", "pipe:1",  # Progress to stdout
        "-i", str(input_path),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    for line in process.stdout:
        # Parse progress lines like "out_time_ms=123456"
        if line.startswith("out_time_ms="):
            time_us = int(line.split("=")[1])
            time_s = time_us / 1_000_000
            progress = min(time_s / duration, 1.0) if duration > 0 else 0
            progress_callback(progress)
    
    process.wait()
    
    if process.returncode != 0:
        raise MediaFormatError(...)
    
    return output_path
```

---

## 5. Common Pitfalls

### Pitfall 1: ffprobe returns 0 for corrupted files

**Issue:** ffprobe may succeed on partially corrupted files.

**Mitigation:**
- Validate duration > 0
- Check for required streams (audio stream for audio files)
- Consider probing a sample with ffmpeg to verify playability

### Pitfall 2: ffmpeg seeking accuracy

**Issue:** Seeking before `-i` is fast but may be inaccurate for some codecs.

**Mitigation:**
- For precise seeking, use `-ss` after `-i` (slower but accurate)
- Phase 3 requirement doesn't specify precision, so fast seeking is acceptable
- Document this limitation

### Pitfall 3: Windows path handling

**Issue:** Windows paths may not be correctly escaped.

**Mitigation:**
- Always use `str(path)` on Path objects
- subprocess handles argument quoting on Windows
- Test on Windows or use CI with Windows runner

### Pitfall 4: Large file timeout

**Issue:** Probing large files (>1GB) can take time.

**Mitigation:**
- Add configurable timeout
- REQUIREMENTS.md specifies < 5 seconds for < 1GB
- Consider warning if timeout is approaching

### Pitfall 5: ffmpeg not found

**Issue:** ffmpeg may not be installed or not in PATH.

**Mitigation:**
- Check for ffmpeg existence before use
- Provide clear error message with installation instructions
- Add to MediaError or create specific MediaToolError

**Pattern:**
```python
def validate_ffprobe_available(ffprobe_path: str) -> None:
    """Validate ffprobe is available."""
    try:
        result = subprocess.run(
            [ffprobe_path, "-version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise MediaError("ffprobe not available")
    except FileNotFoundError:
        raise MediaError(
            f"ffprobe not found at {ffprobe_path}",
            suggestions=[
                "Install ffmpeg (includes ffprobe)",
                "Set AUDIOCORE_FFPROBE_PATH environment variable",
                "Add ffmpeg to your PATH",
            ],
        )
```

### Pitfall 6: Temp file cleanup on crash

**Issue:** If process crashes, temp files remain.

**Mitigation:**
- Use try/finally blocks
- Use context managers
- Phase 9 Pipeline will handle cleanup lifecycle

---

## 6. Dependencies

### External Dependencies

**System requirements:**
- ffmpeg (includes ffprobe)
- Must be in PATH or configured via AppConfig

**Python dependencies (already in project):**
- `pathlib` (stdlib) — file path handling
- `subprocess` (stdlib) — ffmpeg/ffprobe execution
- `json` (stdlib) — ffprobe output parsing
- `tempfile` (stdlib) — temp file management
- `typing` (stdlib) — type hints

**No new external Python dependencies needed for Phase 3.**

### Internal Dependencies (from Phases 1-2)

| Dependency | Location | Usage |
|------------|----------|-------|
| `MediaInfo` | `src/audiocore/models/media.py` | Return type for probe() |
| `MediaFormatError` | `src/audiocore/errors/input.py` | Unsupported format errors |
| `MediaError` | Needs creation | General media errors (extends ProcessingError) |
| `AppConfig` | `src/audiocore/config/settings.py` | ffprobe_path, ffmpeg_path config |

### New Types Needed

**MediaError exception (extends ProcessingError):**
```python
# Add to src/audiocore/errors/processing.py
class MediaError(ProcessingError):
    """Exception for general media processing errors."""
    error_code: str = "AUD-402"
```

**MediaFormat constants (in media module):**
```python
# src/audiocore/media/formats.py
SUPPORTED_AUDIO_FORMATS = frozenset({"mp3", "wav", "m4a", "flac", "ogg", "aac"})
SUPPORTED_VIDEO_FORMATS = frozenset({"mp4", "mkv", "avi", "mov", "webm"})
SUPPORTED_FORMATS = SUPPORTED_AUDIO_FORMATS | SUPPORTED_VIDEO_FORMATS
```

---

## 7. Testing Strategy

### Unit Testing

**Test probe functionality:**
- Mock subprocess.run to return valid ffprobe JSON
- Mock subprocess.run to return error codes
- Test JSON parsing from ffprobe output
- Test MediaInfo construction from probe data

**Test extract functionality:**
- Mock subprocess.run for successful extraction
- Mock subprocess.run for failed extraction
- Test parameter building (seeking, duration, sample rate)
- Test progress callback invocation

**Test format validation:**
- Test extension-based format detection
- Test supported format list membership

### Integration Testing

**FFmpeg/ffprobe availability tests:**
- Skip tests if ffmpeg not available (use `pytest.mark.skipif`)
- Test real probing of sample files
- Test real extraction of sample files

**Test fixtures:**
- Small MP3 file (few seconds)
- Small WAV file (few seconds)
- Small MP4 file (video with audio)
- Corrupted sample file (for error handling)

**Test file structure:**
```
tests/fixtures/media/
    sample.mp3      # Audio-only file
    sample.wav      # Uncompressed audio
    sample.mp4      # Video with audio
    corrupted.mp3   # Invalid file
```

### Test Helpers

```python
# tests/conftest.py
import pytest
import shutil

@pytest.fixture
def ffprobe_available():
    """Check if ffprobe is available."""
    return shutil.which("ffprobe") is not None

@pytest.fixture
def ffmpeg_available():
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None
```

### Test Coverage Goals

- probe() with valid file
- probe() with missing file
- probe() with corrupted file
- probe() with unsupported format
- extract() with valid file
- extract() with seeking
- extract() with duration limit
- extract() progress callback
- is_format_supported() for various extensions
- MediaError exception handling

---

## 8. File Structure Recommendations

### Source Files

```
src/audiocore/
    media/
        __init__.py       # Public API exports
        probe.py           # probe() function implementation
        extractor.py      # extract_audio() function implementation
        formats.py        # Format validation and constants
        exceptions.py     # MediaError exception (or add to processing.py)
```

### Test Files

```
tests/
    unit/
        test_media_probe.py      # Unit tests for probe()
        test_media_extractor.py  # Unit tests for extract_audio()
        test_media_formats.py    # Unit tests for format validation
    integration/
        test_media_integration.py # Real ffmpeg/ffprobe tests
    fixtures/
        media/
            sample.mp3            # Test audio file
            sample.wav            # Test WAV file
            sample.mp4            # Test video file
            corrupted.mp3         # Corrupted test file
```

### Configuration Changes

```python
# src/audiocore/config/settings.py
# Add fields:
    ffprobe_path: str = Field(
        default="ffprobe",
        description="Path to ffprobe binary (e.g., /usr/bin/ffprobe)",
    )
    ffmpeg_path: str = Field(
        default="ffmpeg",
        description="Path to ffmpeg binary (e.g., /usr/bin/ffmpeg)",
    )
```

### Module Exports

```python
# src/audiocore/media/__init__.py
from audiocore.media.probe import probe
from audiocore.media.extractor import extract_audio
from audiocore.media.formats import (
    is_format_supported,
    SUPPORTED_AUDIO_FORMATS,
    SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_FORMATS,
)

__all__ = [
    "probe",
    "extract_audio",
    "is_format_supported",
    "SUPPORTED_AUDIO_FORMATS",
    "SUPPORTED_VIDEO_FORMATS",
    "SUPPORTED_FORMATS",
]
```

---

## Summary

Phase 3 implementation requires:

1. **External tool integration:** subprocess calls to ffprobe/ffmpeg
2. **JSON parsing:** ffprobe output to MediaInfo model mapping
3. **Audio normalization:** ffmpeg conversion to 16kHz mono WAV
4. **Error handling:** MediaFormatError for unsupported formats, MediaError for processing failures
5. **Format validation:** Extension-based pre-filter + ffprobe validation
6. **Progress tracking:** stderr parsing for extraction progress
7. **Temp file management:** NamedTemporaryFile with explicit cleanup

**Key technical decisions:**
- Synchronous subprocess.run (async is Phase 10)
- JSON ffprobe output for reliable parsing
- Temp files with context manager cleanup
- ffprobe_path/ffmpeg_path in AppConfig for flexibility

**Dependencies needed:**
- MediaError exception (add to processing.py)
- New media/ module with probe, extractor, formats submodules
- Test fixtures for real media files

**No new external Python dependencies required.**