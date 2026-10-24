"""FFmpeg/ffprobe wrappers.

* probe(): duration + which streams exist (also our content sniffing: a file
  ffprobe cannot parse as media is rejected).
* extract_audio(): any audio/video -> 16 kHz mono WAV for the transcriber.
* make_playback_audio(): compact AAC (.m4a) for the in-browser player.
* split_audio(): fixed-length pieces (for API size limits), with offsets.

Uploaded files are only ever *read* by ffmpeg; nothing is executed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


class AudioExtractionError(RuntimeError):
    pass


@dataclass
class MediaInfo:
    duration: float
    has_audio: bool
    has_video: bool
    format_name: str


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


async def _run(args: list[str], timeout: float) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, stdin=asyncio.subprocess.DEVNULL
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise AudioExtractionError(f"{Path(args[0]).name} timed out after {int(timeout)}s")
    return proc.returncode, out, err


async def probe(path: str | Path, timeout: float = 60) -> MediaInfo:
    if not ffmpeg_available():
        raise AudioExtractionError("FFmpeg is not installed on the server. See README → FFmpeg setup.")
    code, out, err = await _run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], timeout
    )
    if code != 0:
        raise AudioExtractionError("The file could not be read as audio or video (it may be corrupt or not a media file).")
    data = json.loads(out or b"{}")
    streams = data.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_video = any(
        s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic") for s in streams
    )
    fmt = data.get("format", {})
    try:
        duration = float(fmt.get("duration") or 0)
    except ValueError:
        duration = 0.0
    if duration <= 0:
        for s in streams:
            try:
                duration = max(duration, float(s.get("duration") or 0))
            except ValueError:
                pass
    return MediaInfo(duration=duration, has_audio=has_audio, has_video=has_video, format_name=fmt.get("format_name", ""))


async def extract_audio(src: str | Path, dst_wav: str | Path, timeout: float = 3600) -> Path:
    """Decode the audio track of any supported file to 16 kHz mono PCM WAV."""
    dst_wav = Path(dst_wav)
    code, _, err = await _run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst_wav)],
        timeout,
    )
    if code != 0 or not dst_wav.exists() or dst_wav.stat().st_size < 1000:
        msg = (err or b"").decode("utf-8", "ignore").strip().splitlines()[-1:] or ["unknown error"]
        raise AudioExtractionError(f"Audio extraction failed: {msg[0][:200]}")
    return dst_wav


async def make_playback_audio(src: str | Path, dst: str | Path, timeout: float = 3600) -> Path:
    dst = Path(dst)
    code, _, err = await _run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-vn", "-ac", "1", "-ar", "44100", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(dst)],
        timeout,
    )
    if code != 0 or not dst.exists():
        raise AudioExtractionError("Could not create the playback audio file.")
    return dst


async def split_audio(src_wav: str | Path, out_dir: str | Path, piece_seconds: int = 600,
                      timeout: float = 3600) -> list[tuple[Path, float]]:
    """Split into MP3 pieces (small enough for API upload limits). Returns (path, offset)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = await probe(src_wav)
    pieces: list[tuple[Path, float]] = []
    start = 0.0
    i = 0
    while start < max(info.duration, 0.01):
        dst = out_dir / f"piece_{i:03d}.mp3"
        code, _, _ = await _run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-t", str(piece_seconds),
             "-i", str(src_wav), "-ac", "1", "-ar", "16000", "-b:a", "48k", str(dst)],
            timeout,
        )
        if code != 0:
            raise AudioExtractionError("Failed to split audio for transcription.")
        pieces.append((dst, start))
        start += piece_seconds
        i += 1
    return pieces
