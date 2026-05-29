"""Safe rendering of file paths as ffmpeg/ffprobe command-line arguments.

ffmpeg and ffprobe treat any argument that begins with ``-`` as an option flag.
A media file whose path starts with ``-`` would therefore be parsed as an
(unknown) option instead of a filename — a CWE-88 argument-injection hazard
when the path originates from untrusted input. Routing every file argument
through :func:`as_file_argument` keeps such paths addressing the same file
while guaranteeing the leading character is never ``-``.
"""

from __future__ import annotations

from pathlib import Path


def as_file_argument(path: Path | str) -> str:
    """Render a path as an ffmpeg/ffprobe argument that cannot be read as an option.

    Relative paths beginning with ``-`` are prefixed with ``./`` so they still
    resolve to the same file without their leading ``-`` being treated as an
    option flag. Absolute paths (and any path not starting with ``-``) are
    returned unchanged.

    Example:
        >>> as_file_argument(Path("audio.wav"))
        'audio.wav'
        >>> as_file_argument(Path("-weird.wav"))
        './-weird.wav'
    """
    text = str(path)
    if text.startswith("-"):
        return f"./{text}"
    return text
