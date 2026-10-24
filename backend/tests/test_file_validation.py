import pytest

from app.utils.files import FileValidationError, validate_upload_meta

MB = 1024 * 1024


@pytest.mark.parametrize("name,ctype", [("a.mp3", "audio/mpeg"), ("b.WAV", "audio/wav"), ("c.m4a", "audio/mp4"),
                                         ("d.mp4", "video/mp4"), ("e.mov", "video/quicktime"), ("f.webm", "video/webm"),
                                         ("g.mp3", None), ("h.ogg", "application/ogg")])
def test_allowed(name, ctype):
    assert validate_upload_meta(name, ctype, 10 * MB, 100 * MB)


@pytest.mark.parametrize("name,ctype", [("a.exe", "application/octet-stream"), ("b.pdf", "application/pdf"),
                                         ("c.mp3", "text/html"), ("noext", "audio/mpeg"), ("d.py", "text/x-python")])
def test_rejected_types(name, ctype):
    with pytest.raises(FileValidationError) as e:
        validate_upload_meta(name, ctype, MB, 100 * MB)
    assert e.value.status_code == 415


def test_size_limits():
    with pytest.raises(FileValidationError) as e:
        validate_upload_meta("a.mp3", "audio/mpeg", 101 * MB, 100 * MB)
    assert e.value.status_code == 413
    with pytest.raises(FileValidationError):
        validate_upload_meta("a.mp3", "audio/mpeg", 0, 100 * MB)


async def test_upload_rejects_non_media_disguised_as_mp3(client, alice, db):
    files = {"file": ("lecture.mp3", b"this is not audio at all" * 100, "audio/mpeg")}
    r = await client.post("/api/lectures/upload", files=files, headers=alice)
    assert r.status_code == 415
    assert "could not be read" in r.json()["error"]["message"]
    assert await db.lectures.count_documents({}) == 0


async def test_upload_rejects_wrong_extension(client, alice):
    r = await client.post("/api/lectures/upload", files={"file": ("notes.txt", b"hello", "text/plain")}, headers=alice)
    assert r.status_code == 415


async def test_upload_rejects_oversize(client, alice, monkeypatch, speech_wav):
    from app.core import config
    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    config.get_settings.cache_clear()
    r = await client.post("/api/lectures/upload", files={"file": ("a.wav", speech_wav.read_bytes(), "audio/wav")}, headers=alice)
    assert r.status_code == 413
