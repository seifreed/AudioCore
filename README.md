# AudioCore

Audio transcription library with automatic backend selection.

## Features

- Automatic backend selection (cloud vs local)
- Audio extraction from various formats
- Voice Activity Detection (VAD) segmentation
- Multiple output formats (text, JSON, SRT, VTT)

## Installation

```bash
pip install audiocore
```

## Usage

```python
from audiocore import transcribe

result = transcribe("audio.mp3")
print(result.text)
```

## License

MIT