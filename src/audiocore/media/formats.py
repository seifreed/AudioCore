"""Media format definitions and validation for AudioCore.

This module defines which audio and video formats are supported by AudioCore,
and provides validation utilities for format checking.
"""

from pathlib import Path

from audiocore.errors.input import MediaFormatError

# Supported audio formats for transcription
SUPPORTED_AUDIO_FORMATS: frozenset[str] = frozenset(
    {
        "mp3",  # MPEG Audio Layer III
        "wav",  # Waveform Audio File Format
        "m4a",  # MPEG-4 Audio
        "flac",  # Free Lossless Audio Codec
        "ogg",  # Ogg Vorbis
        "aac",  # Advanced Audio Coding
    }
)

# Supported video formats (audio will be extracted)
SUPPORTED_VIDEO_FORMATS: frozenset[str] = frozenset(
    {
        "mp4",  # MPEG-4 Part 14
        "mkv",  # Matroska Video
        "avi",  # Audio Video Interleave
        "mov",  # QuickTime File Format
        "webm",  # WebM
    }
)

# All supported formats
SUPPORTED_FORMATS: frozenset[str] = SUPPORTED_AUDIO_FORMATS | SUPPORTED_VIDEO_FORMATS


def is_format_supported(file_path: Path | str) -> bool:
    """Check if file format is supported based on extension.

    Args:
        file_path: Path to media file (string or Path object)

    Returns:
        True if format extension is in SUPPORTED_FORMATS, False otherwise

    Example:
        >>> is_format_supported("audio.mp3")
        True
        >>> is_format_supported("video.mp4")
        True
        >>> is_format_supported("document.pdf")
        False
    """
    path = Path(file_path)
    extension = path.suffix.lower().lstrip(".")
    return extension in SUPPORTED_FORMATS


def validate_format_or_raise(file_path: Path | str) -> None:
    """Validate file format and raise MediaFormatError if unsupported.

    Args:
        file_path: Path to media file (string or Path object)

    Raises:
        MediaFormatError: If format is not supported, with actionable suggestions

    Example:
        >>> validate_format_or_raise("audio.mp3")  # No exception raised
        >>> validate_format_or_raise("video.xyz")  # Raises MediaFormatError
        MediaFormatError: Unsupported media format: xyz
    """
    path = Path(file_path)
    if not is_format_supported(path):
        extension = path.suffix.lower().lstrip(".")
        raise MediaFormatError(
            f"Unsupported media format: {extension}",
            context={
                "file_path": str(path),
                "format": extension,
                "supported_formats": sorted(SUPPORTED_FORMATS),
            },
            suggestions=[
                f"Convert to a supported format: {', '.join(sorted(SUPPORTED_FORMATS))}",
                "Use ffprobe to check file compatibility",
                "Install additional codecs if needed",
            ],
        )
