"""Optional pyannote.audio-backed speaker diarization.

``PyannoteDiarizer`` wraps the ``pyannote/speaker-diarization`` pretrained
pipeline behind the :class:`~audiocore.diarization.base.Diarizer` protocol. Both
``pyannote.audio`` and a Hugging Face access token are required at use time and
imported lazily, so the heavy (and gated) dependency is never loaded unless
diarization is actually requested.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from audiocore.diarization.base import SpeakerTurn
from audiocore.errors import ProcessingError

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PYANNOTE_MODEL = "pyannote/speaker-diarization-3.1"


class PyannoteDiarizer:
    """Speaker diarization via the pyannote.audio pretrained pipeline.

    Example:
        >>> diarizer = PyannoteDiarizer(auth_token="hf_...")
        >>> # turns = diarizer.diarize("meeting.wav")
    """

    def __init__(
        self,
        auth_token: str | None = None,
        model: str = DEFAULT_PYANNOTE_MODEL,
        num_speakers: int | None = None,
    ) -> None:
        """Initialize the diarizer (the model loads lazily on first use).

        Args:
            auth_token: Hugging Face access token with access to the gated
                pyannote model. Falls back to the ``HUGGINGFACE_TOKEN`` or
                ``HF_TOKEN`` environment variable when None.
            model: Pretrained pipeline identifier on the Hugging Face Hub.
            num_speakers: Optional fixed speaker count passed to the pipeline.
        """
        self._auth_token = auth_token
        self._model = model
        self._num_speakers = num_speakers
        self._pipeline: Any | None = None

    def diarize(self, audio_path: Path | str) -> list[SpeakerTurn]:
        """Return speaker turns for the given audio file.

        Raises:
            ProcessingError: If pyannote.audio is missing, no token is
                available, or the pipeline fails to load or run.
        """
        pipeline = self._get_pipeline()
        kwargs: dict[str, object] = {}
        if self._num_speakers is not None:
            kwargs["num_speakers"] = self._num_speakers
        try:
            annotation = pipeline(str(audio_path), **kwargs)
        except Exception as run_error:
            raise ProcessingError(
                f"Speaker diarization failed: {run_error}",
                context={"file_path": str(audio_path), "model": self._model},
                suggestions=[
                    "Verify the audio file is valid 16kHz mono WAV",
                    "Check available memory for the diarization model",
                ],
            ) from run_error
        return _annotation_to_turns(annotation)

    def _get_pipeline(self) -> Any:
        """Load and cache the pyannote pipeline, validating prerequisites."""
        if self._pipeline is not None:
            return self._pipeline

        try:
            from pyannote.audio import Pipeline as PyannotePipeline
        except ImportError as import_error:
            raise ProcessingError(
                "The 'pyannote.audio' package is required for speaker diarization",
                context={"import_error": str(import_error)},
                suggestions=[
                    "Install it: pip install audiocore[diarization]",
                    "Or install pyannote.audio directly: pip install pyannote.audio",
                ],
            ) from import_error

        token = self._resolve_token()
        if token is None:
            raise ProcessingError(
                "A Hugging Face access token is required for the pyannote model",
                context={"model": self._model},
                suggestions=[
                    "Pass auth_token=... to PyannoteDiarizer",
                    "Set HUGGINGFACE_TOKEN or HF_TOKEN in the environment",
                    "Accept the model's user conditions on its Hugging Face page",
                ],
            )

        try:
            self._pipeline = PyannotePipeline.from_pretrained(self._model, use_auth_token=token)
        except Exception as load_error:
            raise ProcessingError(
                f"Failed to load diarization model '{self._model}': {load_error}",
                context={"model": self._model},
                suggestions=[
                    "Confirm the token has access to the gated model",
                    "Check network connectivity for the first download",
                ],
            ) from load_error
        return self._pipeline

    def _resolve_token(self) -> str | None:
        """Resolve the HF token from the constructor or environment."""
        if self._auth_token and self._auth_token.strip():
            return self._auth_token.strip()
        import os

        for env_var in ("HUGGINGFACE_TOKEN", "HF_TOKEN"):
            value = os.environ.get(env_var)
            if value and value.strip():
                return value.strip()
        return None


def _annotation_to_turns(annotation: Any) -> list[SpeakerTurn]:
    """Convert a pyannote Annotation into SpeakerTurn objects."""
    turns: list[SpeakerTurn] = []
    for segment, _track, speaker in annotation.itertracks(yield_label=True):
        turns.append(
            SpeakerTurn(
                start_time=float(segment.start),
                end_time=float(segment.end),
                speaker=str(speaker),
            )
        )
    return turns
