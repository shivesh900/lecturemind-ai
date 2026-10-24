import pytest

from app.services.transcript_processor import build_chunks, clean_segments
from app.services.transcription_service import LocalWhisperTranscriber, OpenAITranscriber


@pytest.mark.slow
async def test_local_whisper_transcribes_real_speech(speech_wav, tmp_path):
    """Real speech-to-text with faster-whisper `tiny` on the espeak fixture."""
    from app.services.audio_extractor import extract_audio
    wav = await extract_audio(speech_wav, tmp_path / "w.wav")
    res = await LocalWhisperTranscriber("tiny").transcribe(wav, language="en")
    text = res.text.lower()
    assert res.provider == "local" and res.segments
    assert "speech" in text and "language" in text and "model" in text
    assert all(s.end >= s.start for s in res.segments)
    assert res.segments[0].speaker is None  # no invented speakers


class _Resp:
    def __init__(self, data):
        self._d = data

    def model_dump(self):
        return self._d


class _FakeAudioAPI:
    def __init__(self):
        self.calls = 0

    async def create(self, **kw):
        self.calls += 1
        assert kw["response_format"] == "verbose_json"
        return _Resp({"language": "english", "segments": [{"start": 0.0, "end": 1.5, "text": " Hello class."},
                                                           {"start": 1.5, "end": 2.5, "text": "Today: HMMs."}]})


class _FakeOpenAI:
    def __init__(self):
        self.audio = type("A", (), {})()
        self.audio.transcriptions = _FakeAudioAPI()


async def test_openai_transcriber_offsets_pieces(speech_wav, tmp_path, monkeypatch):
    """The OpenAI path splits long audio and shifts each piece's timestamps (mocked API)."""
    import shutil
    from app.services import audio_extractor
    wav = tmp_path / "a.wav"
    shutil.copy(speech_wav, wav)
    orig = audio_extractor.split_audio
    monkeypatch.setattr(audio_extractor, "split_audio", lambda src, out, piece_seconds=600: orig(src, out, piece_seconds=3))
    fake = _FakeOpenAI()
    res = await OpenAITranscriber(client=fake).transcribe(wav)
    n = fake.audio.transcriptions.calls
    assert n >= 2 and len(res.segments) == 2 * n
    assert res.segments[2].start == pytest.approx(3.0)
    assert res.provider == "openai"


def test_clean_and_chunk_preserve_order_and_time():
    long = " ".join(f"Sentence number {i} is here." for i in range(60))
    segs = clean_segments([{"start": 0, "end": 10, "text": "  Hello   world. "}, {"start": 10, "end": 70, "text": long},
                           {"start": 70, "end": 72, "text": ""}])
    assert segs[0]["text"] == "Hello world."
    assert len(segs) > 2  # long segment split on sentences
    assert [s["idx"] for s in segs] == list(range(len(segs)))
    assert all(a["start"] <= b["start"] for a, b in zip(segs, segs[1:]))
    chunks = build_chunks(segs, target_chars=400, overlap_segments=1)
    assert len(chunks) > 1
    assert chunks[0].start == 0 and chunks[-1].end == pytest.approx(70, abs=0.01)
    assert all(c.seg_start <= c.seg_end for c in chunks)
    assert all(a.seg_start < b.seg_start for a, b in zip(chunks, chunks[1:]))
