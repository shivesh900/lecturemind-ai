import wave

from app.services import audio_extractor


async def test_probe_audio(speech_wav):
    info = await audio_extractor.probe(speech_wav)
    assert info.has_audio and not info.has_video
    assert 2 < info.duration < 20


async def test_extract_audio_from_video(tmp_path, speech_mp4):
    info = await audio_extractor.probe(speech_mp4)
    assert info.has_video and info.has_audio
    out = await audio_extractor.extract_audio(speech_mp4, tmp_path / "out.wav")
    with wave.open(str(out)) as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 16000
        assert w.getnframes() / 16000 > 2


async def test_playback_and_split(tmp_path, speech_wav):
    m4a = await audio_extractor.make_playback_audio(speech_wav, tmp_path / "p.m4a")
    assert m4a.stat().st_size > 1000
    pieces = await audio_extractor.split_audio(speech_wav, tmp_path / "pieces", piece_seconds=3)
    assert len(pieces) >= 2
    assert [off for _, off in pieces][:2] == [0.0, 3.0]


async def test_corrupt_file_raises(tmp_path):
    bad = tmp_path / "bad.mp3"
    bad.write_bytes(b"\x00" * 2048)
    try:
        await audio_extractor.probe(bad)
    except audio_extractor.AudioExtractionError as e:
        assert "could not be read" in str(e)
    else:
        raise AssertionError("expected AudioExtractionError")
