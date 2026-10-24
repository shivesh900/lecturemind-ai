"""Test setup.

* MongoDB is replaced by mongomock-motor (in-memory), so no database server is
  needed. Set TEST_MONGODB_URI to run the same tests against a real MongoDB.
* No paid API is called: OPENAI_API_KEY is blanked, and AI tests inject a fake
  LLM client (see FakeLLM below).
* Local Whisper uses the `tiny` model on tests/fixtures/speech_sample.wav.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="lecturemind-test-")
os.environ.update({
    "ENVIRONMENT": "test",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "STORAGE_DIR": _TMP,
    "WHISPER_MODEL": "tiny",
    "JWT_SECRET": "test-secret-not-for-production-0123456789",
    "JOB_RETRY_BASE_SECONDS": "0",
    "AI_RATE_LIMIT_PER_MINUTE": "1000",
    "AUTH_RATE_LIMIT_PER_MINUTE": "1000",
    "TRANSCRIPTION_PROVIDER": "local",
})

import httpx  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402

from app.core import config  # noqa: E402

config.get_settings.cache_clear()

from app.core.database import set_database  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import llm_client  # noqa: E402
from app.services.storage_service import reset_storage  # noqa: E402
from app.workers.queue import job_queue  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
SPEECH_WAV = FIXTURES / "speech_sample.wav"


@pytest.fixture(autouse=True)
async def _fresh_state(monkeypatch):
    if os.environ.get("TEST_MONGODB_URI"):
        from motor.motor_asyncio import AsyncIOMotorClient
        mc = AsyncIOMotorClient(os.environ["TEST_MONGODB_URI"])
        await mc.drop_database("lecturemind_test")
        db = mc["lecturemind_test"]
        from app.core.database import init_indexes
        await init_indexes(db)
    else:
        db = AsyncMongoMockClient()["lecturemind_test"]
    set_database(db)
    limiter.reset()
    reset_storage()
    job_queue.inline = True  # uploads are processed synchronously in tests
    llm_client.set_llm_client(None)
    config.get_settings.cache_clear()
    yield db
    llm_client.set_llm_client(None)
    config.get_settings.cache_clear()


@pytest.fixture
def db(_fresh_state):
    return _fresh_state


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register(client, email="alice@example.com", name="Alice", password="password123"):
    r = await client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.fixture
async def alice(client):
    token = await register(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def bob(client):
    token = await register(client, "bob@example.com", "Bob")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def speech_wav() -> Path:
    assert SPEECH_WAV.exists(), "run tests/fixtures/make_fixture.sh"
    return SPEECH_WAV


@pytest.fixture
def speech_mp4(tmp_path, speech_wav) -> Path:
    """A real video file (solid colour + the speech fixture) generated with ffmpeg."""
    out = tmp_path / "lecture.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=navy:s=320x240:r=5",
                    "-i", str(speech_wav), "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(out)], check=True)
    return out


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


# ---------------------------------------------------------------- fake LLM
class FakeLLM(llm_client.LLMClient):
    """Returns schema-valid canned objects so generation code can be tested without
    a paid API. `responses` maps schema name -> callable(prompt) -> dict."""

    def __init__(self, responses=None, fail_with: Exception | None = None):
        super().__init__(client=object())
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []
        self.fail_with = fail_with

    async def chat_json(self, system, user, schema, **kw):
        self.calls.append((schema.__name__, user))
        if self.fail_with:
            raise self.fail_with
        fn = self.responses.get(schema.__name__) or DEFAULTS[schema.__name__]
        return schema.model_validate(fn(user))

    async def embed(self, texts, batch_size=64):
        # deterministic bag-of-letters vectors
        out = []
        for t in texts:
            v = [0.0] * 26
            for ch in t.lower():
                if "a" <= ch <= "z":
                    v[ord(ch) - 97] += 1
            out.append(v)
        return out


DEFAULTS = {
    "ChunkDigest": lambda u: {"title": "Speech recognition basics", "summary": "The lecture explains speech recognition.",
                              "key_points": ["Speech recognition converts speech to text"],
                              "definitions": [{"term": "Acoustic model", "definition": "Maps audio to sounds"}],
                              "formulas": [], "examples": [], "concepts": ["acoustic model", "language model"],
                              "entities": []},
    "LectureSummary": lambda u: {"executive_summary": "Overview of speech recognition.",
                                 "quick_summary": ["a", "b", "c", "d", "e", "f"],
                                 "detailed_summary": [{"heading": "Intro", "content": "Speech to text."}],
                                 "main_topics": [{"title": "ASR", "description": "", "chunk_index": 0}],
                                 "key_takeaways": ["Models work together"]},
    "StudyNotesOut": lambda u: {"title": "Notes", "sections": [{"heading": "Acoustic model", "chunk_index": 0,
                                "bullets": ["• Maps audio to phonemes"], "steps": ["1. Extract features"]}],
                                "terminology": [{"term": "ASR", "definition": "Automatic speech recognition"}],
                                "revision_summary": ["Know both models"]},
    "QuizOut": lambda u: {"title": "Quiz", "questions": [
        {"type": "mcq", "question": "What converts speech to text?", "options": ["A) Speech recognition", "B) Compiler", "C) Router", "D) Kernel"],
         "correct_answer": "A", "explanation": "Stated in the lecture."},
        {"type": "true_false", "question": "The language model works alone.", "options": ["True", "False"], "correct_answer": "false"},
        {"type": "mcq", "question": "Broken question", "options": ["x", "y"], "correct_answer": "x"},
        {"type": "short", "question": "Define acoustic model.", "correct_answer": "Maps audio to sounds."},
    ]},
    "FlashcardsOut": lambda u: {"cards": [{"front": "ASR?", "back": "Automatic speech recognition"},
                                          {"front": "asr?", "back": "duplicate"}, {"front": "", "back": "empty"}]},
    "KnowledgeMapOut": lambda u: {"nodes": [{"id": "n1", "label": "Speech recognition", "type": "topic", "chunk_index": 0},
                                            {"id": "n2", "label": "Acoustic model", "type": "concept", "chunk_index": 0}],
                                  "edges": [{"source": "n1", "target": "n2", "relation": "uses"},
                                            {"source": "n1", "target": "ghost", "relation": "bad"}],
                                  "keywords": ["speech"]},
    "ChatAnswer": lambda u: {"answer": "It converts speech to text.", "supported": True, "cited_excerpts": [1]},
}


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLM()
    llm_client.set_llm_client(fake)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    config.get_settings.cache_clear()
    yield fake
    llm_client.set_llm_client(None)
