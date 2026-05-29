"""Live audio sources for real-time transcription.

``AudioSource`` is the structural contract a live capture source must satisfy:
an iterable that yields mono float32 PCM chunks at a known sample rate. The
bundled :class:`MicrophoneSource` captures from the default input device via the
optional ``sounddevice`` dependency; tests and custom integrations can supply
any iterable of chunks (e.g. a socket stream or a pre-recorded buffer).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np

from audiocore.errors import ProcessingError
from audiocore.realtime.segmenter import REALTIME_SAMPLE_RATE

if TYPE_CHECKING:
    from collections.abc import Iterator

    from numpy.typing import NDArray

# Default capture block: 30 ms at 16 kHz keeps latency low while giving the
# energy gate a stable RMS window.
DEFAULT_BLOCK_SECONDS = 0.03


@runtime_checkable
class AudioSource(Protocol):
    """Structural interface for a stream of live audio chunks.

    Iterating the source yields mono float32 arrays normalized to [-1, 1]. The
    ``sample_rate`` attribute reports the rate of those chunks in Hz.
    """

    sample_rate: int

    def __iter__(self) -> Iterator[NDArray[np.float32]]:
        """Yield successive mono float32 audio chunks until the stream ends."""
        ...


class MicrophoneSource:
    """Capture audio from the default input device via ``sounddevice``.

    The source yields fixed-size mono float32 blocks until ``stop()`` is called
    (or the surrounding iteration is abandoned). ``sounddevice`` is imported
    lazily so the dependency is only required when live capture is actually used.

    Example:
        >>> from audiocore.realtime import MicrophoneSource, RealtimeTranscriber
        >>> mic = MicrophoneSource()
        >>> # for segment in RealtimeTranscriber(backend).stream(mic): ...
    """

    def __init__(
        self,
        sample_rate: int = REALTIME_SAMPLE_RATE,
        block_seconds: float = DEFAULT_BLOCK_SECONDS,
        device: int | str | None = None,
    ) -> None:
        """Initialize a microphone source.

        Args:
            sample_rate: Capture sample rate in Hz (16 kHz matches the backends).
            block_seconds: Duration of each yielded block in seconds.
            device: Optional input device index/name for ``sounddevice``.
        """
        self.sample_rate = sample_rate
        self._block_frames = max(1, int(block_seconds * sample_rate))
        self._device = device
        self._stopped = False

    def stop(self) -> None:
        """Request that iteration stop after the current block."""
        self._stopped = True

    def __iter__(self) -> Iterator[NDArray[np.float32]]:
        """Yield mono float32 blocks captured from the input device.

        Raises:
            ProcessingError: If ``sounddevice`` is not installed or the input
                stream cannot be opened.
        """
        try:
            import sounddevice as sd
        except ImportError as import_error:
            raise ProcessingError(
                "The 'sounddevice' package is required for microphone capture",
                context={"import_error": str(import_error)},
                suggestions=[
                    "Install it: pip install sounddevice",
                    "Or feed a custom AudioSource (any iterable of float32 chunks)",
                ],
            ) from import_error

        self._stopped = False
        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self._block_frames,
                device=self._device,
            ) as stream:
                while not self._stopped:
                    data, _overflowed = stream.read(self._block_frames)
                    yield np.asarray(data, dtype=np.float32).reshape(-1)
        except ProcessingError:
            raise
        except Exception as capture_error:
            raise ProcessingError(
                f"Microphone capture failed: {capture_error}",
                context={"sample_rate": self.sample_rate},
                suggestions=[
                    "Verify an input device is connected and permitted",
                    "Try specifying a device index via the device argument",
                ],
            ) from capture_error
