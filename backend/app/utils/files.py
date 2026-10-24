"""Upload validation: extension, declared MIME, size, and content sniffing via ffprobe."""
from __future__ import annotations

import os

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".webm", ".weba"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
ALLOWED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

ALLOWED_MIME_PREFIXES = ("audio/", "video/")
ALLOWED_MIME_EXACT = {"application/octet-stream", "application/ogg", ""}


class FileValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 415):
        super().__init__(message)
        self.status_code = status_code


def extension_of(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def validate_upload_meta(filename: str, content_type: str | None, size: int | None, max_bytes: int) -> str:
    """Validate what we know before/while reading the body. Returns the extension."""
    ext = extension_of(filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(e.lstrip(".").upper() for e in ALLOWED_EXTENSIONS))
        raise FileValidationError(f"Unsupported file type '{ext or 'none'}'. Allowed: {allowed}.")
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct and not (ct.startswith(ALLOWED_MIME_PREFIXES) or ct in ALLOWED_MIME_EXACT):
        raise FileValidationError(f"Unsupported content type '{ct}'. Upload an audio or video file.")
    if size is not None:
        if size <= 0:
            raise FileValidationError("The file is empty.", 400)
        if size > max_bytes:
            raise FileValidationError(f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.", 413)
    return ext


def media_kind(ext: str, has_video_stream: bool) -> str:
    if has_video_stream and ext in VIDEO_EXTENSIONS:
        return "video"
    return "audio"
