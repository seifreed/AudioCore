# RESEARCH: Phase 4 - VAD Processing

## 1. Domain Analysis

### What is VAD (Voice Activity Detection)?

Voice Activity Detection identifies speech segments in audio, distinguishing speech from silence/noise. For transcription:

- **Purpose**: Only transcribe speech segments, skipping silence → faster processing, lower cost, better accuracy
- **Why Silero**: State-of-the-art VAD model, ~5MB weights, runs on CPU, high accuracy, easy integration
- **Input**: Audio waveform (numpy array at correct sample rate)
- **Output**: Speech segments with timestamps and confidence scores

### Silero VAD Architecture

```
Input Audio (16kHz WAV)
    ↓
torch.hub.load('snakers4/silero-vad', 'silero_vad')
    ↓
model(audio_chunk, sample_rate) → speech probability
    ↓
Collect segments where probability > threshold
    ↓
Post-process (merge, split, pad)
    ↓
Output: List of (start_time, end_time) segments
```

### Key Characteristics

1. **Sample Rate**: Requires 16kHz (matches our extract_audio output)
2. **Chunk Size**: Optimal processing in ~512-1024 sample chunks
3. **Model Size**: ~5MB (~1MB JIT model)
4. **CPU-first**: Designed for CPU inference (no GPU required)
5. **Torch Hub**: Model downloaded via `torch.hub` on first use

### Dependencies to Add

- `torch` (PyTorch) - required for Silero VAD
- `numpy` - audio array manipulation
- `torchaudio` (optional) - if audio loading needed, but we have ffmpeg

## 2. Implementation Strategy

### Three-Plan Architecture (Matches Requirements)

| Plan | Requirement | Scope |
|------|-------------|-------|
| 04-01 | VAD-01 | Silero VAD model integration (lazy loading, torch hub, caching) |
| 04-02 | VAD-02 | VAD parameter configuration (VADConfig model, AppConfig integration) |
| 04-03 | VAD-03 | Segment boundary processing (merge short, split long, gaps, ordering) |

### Plan 04-01: Silero VAD Integration

**Module**: `src/audiocore/vad/silero.py`

**Key Components**:
1. Model loader with lazy initialization
2. Torch hub download with local cache fallback
3. Audio-to-numpy conversion (reuse extract_audio output)
4. Speech probability detection per chunk
5. Segment extraction with confidence

**Patterns to Follow**:
- Lazy model loading (like how we might load ML models)
- Context manager pattern from `temp_audio_file`
- Error wrapping in `VADError` exception

```python
class SileroVAD:
    _model = None  # Singleton pattern for model caching
    
    @classmethod
    def _load_model(cls):
        if cls._model is None:
            cls._model = torch.hub.load('snakers4/silero-vad', 'silero_vad')
        return cls._model
    
    def detect_speech(self, audio_path: Path) -> list[SpeechSegment]:
        ...
```

**Model Download Strategy**:
1. Try torch.hub with network
2. Check local cache directory
3. Raise VADError with offline guidance if both fail

### Plan 04-02: VAD Parameter Configuration

**Module**: `src/audiocore/vad/config.py`

**VADConfig Model**:

```python
class VADConfig(BaseModel):
    model_config = {"strict": True, "extra": "forbid"}
    
    # Segment duration limits
    min_segment_duration: float = Field(default=0.5, ge=0.1, le=10.0)
    max_segment_duration: float = Field(default=30.0, ge=5.0, le=300.0)
    
    # Detection thresholds
    speech_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    silence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Segment padding
    speech_pad_ms: int = Field(default=30, ge=0, le=500)
    
    # Merge/split parameters
    min_silence_duration_ms: int = Field(default=100, ge=50, le=1000)
    window_size_samples: int = Field(default=512, ge=256, le=1024)
```

**Integration with AppConfig**:

Add VadConfig field to `AppConfig`:
```python
vad: VADConfig = Field(default_factory=VADConfig)
```

Add VAD-related env vars:
- `AUDIOCORE_VAD_MIN_SEGMENT_DURATION`
- `AUDIOCORE_VAD_MAX_SEGMENT_DURATION`
- `AUDIOCORE_VAD_SPEECH_THRESHOLD`
- etc.

### Plan 04-03: Segment Boundary Processing

**Module**: `src/audiocore/vad/segments.py`

**Key Operations**:

1. **Raw VAD Output → Segments**: Convert probability stream to binary segments
2. **Merge Short Segments**: Combine segments below `min_segment_duration` if gap < threshold
3. **Split Long Segments**: Break segments above `max_segment_duration` at silence points
4. **Pad Segments**: Add `speech_pad_ms` to start/end of each segment
5. **Gap Filling**: Ensure coverage (no gaps > `min_silence_duration_ms`)
6. **Ordering**: Output in chronological order (already sorted by VAD)

**Algorithm**:

```python
def process_segments(
    vad_output: list[tuple[float, float, float]],  # (start, end, confidence)
    config: VADConfig,
    total_duration: float,
) -> list[Segment]:
    # 1. Filter by confidence threshold
    segments = filter_by_confidence(vad_output, config.speech_threshold)
    
    # 2. Merge short segments
    segments = merge_short_segments(segments, config)
    
    # 3. Split long segments  
    segments = split_long_segments(segments, config)
    
    # 4. Pad segments
    segments = pad_segments(segments, config.speech_pad_ms, total_duration)
    
    # 5. Validate coverage
    validate_coverage(segments, total_duration, config)
    
    return segments
```

**Segment Model Reuse**:
- Use existing `Segment` model from Phase 1
- VAD produces `Segment(start_time, end_time, text="", confidence)`
- Pipeline fills in `text` during transcription

## 3. Technical Decisions

### Decision 1: Model Loading Strategy

**Choice**: Lazy singleton with module-level cache

**Rationale**:
- Avoid loading model on import (slow startup)
- Cache model for repeated calls (memory efficient)
- Allow explicit cleanup if needed

**Implementation**:
```python
class SileroVAD:
    _model: torch.nn.Module | None = None
    _lock = threading.Lock()
    
    @classmethod
    def get_model(cls) -> torch.nn.Module:
        with cls._lock:
            if cls._model is None:
                cls._model = cls._load_model()
            return cls._model
```

### Decision 2: Torch Hub vs Local Cache

**Choice**: Torch hub first, local cache fallback

**Rationale**:
- Torch hub is official distribution method
- Local cache enables offline usage after first download
- Cache location: `~/.cache/torch/hub/snakers4_silero-vad_master/`

**Implementation**:
```python
def _load_model(cls):
    try:
        model = torch.hub.load('snakers4/silero-vad', 'silero_vad')
    except Exception as e:
        # Try local cache
        cache_path = Path.home() / '.cache' / 'torch' / 'hub'
        if cache_path.exists():
            model = torch.hub.load(str(cache_path / 'snakers4_silero-vad_master'), 'silero_vad', source='local')
        else:
            raise VADError(
                "Failed to load Silero VAD model",
                context={"reason": str(e)},
                suggestions=[
                    "Check internet connection for first-time download",
                    "Ensure torch is installed: pip install torch",
                    "Pre-download model: python -c \"import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad')\"",
                ],
                cause=e,
            )
    return model
```

### Decision 3: Audio Input Format

**Choice**: Accept Path to WAV file, load with scipy or torchaudio

**Rationale**:
- extract_audio already produces WAV files
- WAV loading is simpler than numpy array handling
- Single point of audio format handling

**Implementation**:
```python
import scipy.io.wavfile as wav

def _load_audio(self, audio_path: Path) -> tuple[np.ndarray, int]:
    sample_rate, audio_data = wav.read(str(audio_path))
    # Handle stereo by converting to mono
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)
    return audio_data.astype(np.float32), sample_rate
```

### Decision 4: Processing Chunk Size

**Choice**: 512 samples (32ms at 16kHz)

**Rationale**:
- Silero VAD optimized for 512, 768, or 1024 samples
- Smaller chunks = more precise boundaries
- 512 is default and most tested

### Decision 5: Memory Management

**Choice**: Process audio in chunks, not whole file at once

**Rationale**:
- 1-hour audio = ~288MB at 16kHz 16-bit mono
- Process chunk-by-chunk to bound memory
- Stream results to output immediately

## 4. Standard Patterns

### Silero VAD Usage Pattern

```python
import torch

# Load model (lazy, cached)
model = torch.hub.load('snakers4/silero-vad', 'silero_vad')
model.eval()

# Prepare audio chunk
_audio = torch.from_numpy(audio_chunk).float()

# Get speech probability
speech_prob = model(_audio, sample_rate).item()

# Collect segments
segments = []
if speech_prob > threshold:
    # Track segment start/end
    ...
```

### Torch Hub Caching Pattern

```python
# Model cached at:
# ~/.cache/torch/hub/snakers4_silero-vad_master/

# Force reload:
model = torch.hub.load('snakers4/silero-vad', 'silero_vad', force_reload=True)

# Load from local:
model = torch.hub.load('snakers4_silero-vad', 'silero_vad', source='local')
```

### Numpy Audio Processing Pattern

```python
import numpy as np

# Convert to correct dtype
audio = audio.astype(np.float32) / 32768.0  # Normalize 16-bit PCM

# Chunk processing
for i in range(0, len(audio), chunk_size):
    chunk = audio[i:i + chunk_size]
    prob = model(torch.from_numpy(chunk), sample_rate).item()
    ...
```

### Segment Merging Pattern

```python
def merge_short_segments(
    segments: list[Segment],
    min_duration: float,
    max_gap: float,
) -> list[Segment]:
    if not segments:
        return segments
    
    merged = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        gap = seg.start_time - prev.end_time
        
        # Merge if segment is short and gap is small
        if (prev.end_time - prev.start_time) < min_duration and gap < max_gap:
            merged[-1] = Segment(
                start_time=prev.start_time,
                end_time=seg.end_time,
                text="",  # Filled by transcription
                confidence=min(prev.confidence or 1.0, seg.confidence or 1.0),
            )
        else:
            merged.append(seg)
    
    return merged
```

### Segment Splitting Pattern

```python
def split_long_segments(
    segments: list[Segment],
    max_duration: float,
    min_silence: float,
) -> list[Segment]:
    result = []
    for seg in segments:
        duration = seg.end_time - seg.start_time
        if duration <= max_duration:
            result.append(seg)
        else:
            # Split into chunks of max_duration
            # Last chunk takes remainder
            n_chunks = math.ceil(duration / max_duration)
            chunk_duration = duration / n_chunks
            for i in range(n_chunks):
                result.append(Segment(
                    start_time=seg.start_time + i * chunk_duration,
                    end_time=min(seg.end_time, seg.start_time + (i + 1) * chunk_duration),
                    text="",
                    confidence=seg.confidence,
                ))
    return result
```

## 5. Common Pitfalls

### Pitfall 1: Wrong Sample Rate

**Problem**: Silero VAD expects 16kHz. Passing other rates causes incorrect results.

**Solution**: Always use extract_audio's 16kHz output, validate in VAD module.

```python
if sample_rate != 16000:
    raise VADError(
        f"Invalid sample rate: {sample_rate}. Silero VAD requires 16kHz audio.",
        context={"sample_rate": sample_rate, "expected": 16000},
        suggestions=["Use extract_audio() which normalizes to 16kHz"],
    )
```

### Pitfall 2: Integer Audio Values

**Problem**: scipy.io.wavfile returns int16 values, but model expects float32.

**Solution**: Normalize to float32 in range [-1, 1].

```python
audio = audio.astype(np.float32) / 32768.0
```

### Pitfall 3: Stereo Audio

**Problem**: Stereo audio has 2 channels, model expects mono.

**Solution**: Average channels or take first channel.

```python
if len(audio.shape) > 1:
    audio = audio.mean(axis=1)  # Average channels
```

### Pitfall 4: Memory Exhaustion on Long Files

**Problem**: Loading 2-hour audio into memory can exceed RAM.

**Solution**: Stream processing or chunk-based loading.

```python
# For very long files, consider streaming:
# chunk-by-chunk processing with state tracking
```

### Pitfall 5: Overlapping Segments

**Problem**: Naive merge logic can create overlapping segments.

**Solution**: Always validate segment order and non-overlap.

```python
def validate_segments(segments: list[Segment]) -> None:
    for i, seg in enumerate(segments):
        if seg.end_time < seg.start_time:
            raise ValueError(f"Invalid segment {i}: end before start")
        if i > 0 and seg.start_time < segments[i-1].end_time:
            raise ValueError(f"Overlapping segments at index {i}")
```

### Pitfall 6: Model Download Blocking

**Problem**: First VAD call blocks while downloading model.

**Solution**: Document download requirement, provide pre-download command.

```python
# Add to documentation:
# Pre-download VAD model: python -c "import torch; torch.hub.load('snakers4/silero-vad', 'silero_vad')"
```

### Pitfall 7: Thread Safety

**Problem**: Multiple threads calling VAD simultaneously could race on model loading.

**Solution**: Use thread lock for singleton initialization.

```python
import threading

class SileroVAD:
    _lock = threading.Lock()
    _model = None
    
    @classmethod
    def get_model(cls):
        with cls._lock:
            if cls._model is None:
                cls._model = torch.hub.load(...)
        return cls._model
```

### Pitfall 8: Large Segment Near End

**Problem**: Long speech segment near audio end may need splitting differently.

**Solution**: Handle boundary cases explicitly.

### Pitfall 9: Confidence Interpretation

**Problem**: Silero outputs probability per chunk, but we want per-segment confidence.

**Solution**: Aggregate probabilities appropriately (mean, min, weighted).

```python
# Option 1: Mean confidence
confidence = sum(chunk_probs) / len(chunk_probs)

# Option 2: Minimum confidence (conservative)
confidence = min(chunk_probs)
```

## 6. Dependencies

### New Dependencies Required

| Package | Version | Purpose |
|---------|---------|---------|
| `torch` | >=2.0.0 | Silero VAD model runtime |
| `numpy` | >=1.24.0 | Audio array manipulation |
| `scipy` | >=1.10.0 | WAV file reading (optional, can use wave module) |

### Internal Dependencies (From Phase 1-3)

| Module | Dependency |
|--------|------------|
| `audiocore.errors` | `VADError` exception (already defined) |
| `audiocore.models.segment` | `Segment` model (already defined) |
| `audiocore.models.media` | `MediaInfo` model (for duration validation) |
| `audiocore.config` | `AppConfig`, `VADConfig` (new) |
| `audiocore.media.extractor` | `extract_audio()` function |

### Dependency Graph

```
torch.hub → model loading
    ↓
SileroVAD._load_model()
    ↓
SileroVAD.detect_speech(audio_path)
    ↓
SegmentProcessor.process(vad_output, config)
    ↓
list[Segment] (with start_time, end_time, confidence)
```

## 7. Testing Strategy

### Unit Tests

**Module**: `tests/unit/vad/test_silero.py`

1. **Model Loading Tests**:
   - Test lazy loading (model None on import)
   - Test model loaded on first call
   - Test model cached on subsequent calls
   - Test VADError on model load failure (mocked)

2. **Audio Loading Tests**:
   - Test WAV file loading
   - Test stereo to mono conversion
   - Test sample rate validation (error on non-16kHz)
   - Test file not found error

3. **Speech Detection Tests**:
   - Test speech probability detection (mocked model)
   - Test segment extraction from probabilities
   - Test confidence filtering

**Module**: `tests/unit/vad/test_config.py`

1. **Config Validation Tests**:
   - Test default values
   - Test boundary validation (min < max, etc.)
   - Test invalid value rejection
   - Test AppConfig integration

**Module**: `tests/unit/vad/test_segments.py`

1. **Segment Processing Tests**:
   - Test merge short segments
   - Test split long segments
   - Test segment padding
   - Test coverage validation
   - Test temporal ordering
   - Test no-overlap invariant

### Integration Tests

**Module**: `tests/integration/vad/test_vad_integration.py`

1. **End-to-End VAD Tests**:
   - Test with real audio file (requires ffmpeg fixture)
   - Test segment output matches expected ranges
   - Test memory usage on long files

2. **Model Download Tests** (optional, slow):
   - Test torch hub download (may skip in CI)
   - Test local cache fallback

### Test Fixtures

```python
# tests/fixtures/audio.py
@pytest.fixture
def sample_audio_path(tmp_path):
    # Generate test audio with ffmpeg
    # Or use pre-recorded fixture
    ...

@pytest.fixture
def mocked_silero_model():
    # Mock torch.hub.load to return mock model
    with patch('torch.hub.load') as mock_load:
        model = MagicMock()
        model.return_value = MagicMock(item=lambda: 0.85)
        mock_load.return_value = model
        yield model
```

### Test Coverage Goals

- `silero.py`: >95% coverage (model loading, audio processing, VAD)
- `config.py`: 100% coverage (Pydantic model validation)
- `segments.py`: >95% coverage (all merge/split/pad logic)

## 8. File Structure Recommendations

### Recommended Structure

```
src/audiocore/vad/
├── __init__.py           # Public API: detect_speech(), VADConfig
├── silero.py             # Silero VAD model integration
├── config.py             # VADConfig model definition
├── segments.py           # Segment processing utilities
└── audio.py              # Audio loading utilities (optional, could be in silero.py)

src/audiocore/
├── __init__.py           # Update exports
├── config/
│   └── settings.py       # Add vad: VADConfig field to AppConfig
└── ...

tests/unit/vad/
├── __init__.py
├── test_silero.py
├── test_config.py
├── test_segments.py
└── test_audio.py          # If audio.py is separate

tests/integration/vad/
├── __init__.py
└── test_vad_integration.py
```

### Module Responsibilities

| File | Responsibility |
|------|---------------|
| `__init__.py` | Public API exports: `detect_speech`, `VADConfig`, `SegmentProcessor` |
| `silero.py` | Model loading, caching, speech detection |
| `config.py` | `VADConfig` Pydantic model |
| `segments.py` | Segment merging, splitting, padding, validation |
| `audio.py` (optional) | WAV loading, format conversion |

### Public API from `vad/__init__.py`

```python
from audiocore.vad.config import VADConfig
from audiocore.vad.silero import SileroVAD, detect_speech
from audiocore.vad.segments import process_segments

__all__ = [
    "VADConfig",
    "SileroVAD",
    "detect_speech",
    "process_segments",
]
```

### Convenience Function

```python
def detect_speech(
    audio_path: Path | str,
    config: VADConfig | None = None,
) -> list[Segment]:
    """High-level VAD function for speech detection.
    
    Args:
        audio_path: Path to 16kHz mono WAV file.
        config: VAD configuration. Uses defaults if None.
    
    Returns:
        List of Segment objects with start_time, end_time, and confidence.
    
    Raises:
        VADError: If model loading or processing fails.
        InvalidInputError: If file not found or invalid format.
    """
    config = config or VADConfig()
    vad = SileroVAD()
    raw_segments = vad.detect(audio_path, config)
    return process_segments(raw_segments, config)
```

---

## Summary for Planning

**Key Implementation Steps**:

1. **Add dependencies** to `pyproject.toml`: `torch`, `numpy`, `scipy`
2. **Create VADConfig** in `config/` with all VAD parameters
3. **Implement SileroVAD class** with lazy model loading and thread-safe caching
4. **Implement segment processing** with merge/split/pad algorithms
5. **Add VADError handling** for model loading failures and processing errors
6. **Write comprehensive tests** with mocked model and real audio fixtures

**Estimated Complexity**:
- Plan 04-01 (Silero Integration): Medium - requires torch integration
- Plan 04-02 (Config): Low - straightforward Pydantic model
- Plan 04-03 (Segments): Medium - algorithm implementation and edge cases

**Risks**:
- Torch hub network dependency on first run
- Memory usage on very long audio files
- Model download blocking CLI/API first call

**Integration Points**:
- `AppConfig` needs `VADConfig` field
- `extract_audio()` output feeds directly to VAD
- `Segment` model from Phase 1 used for output
- `VADError` exception from Phase 1 for error handling