"""Summary / notes / quiz / flashcards / knowledge map / chat with a mocked LLM."""
import json

import pytest

from app.schemas.ai import ChunkDigest, LectureSummary
from app.services import llm_client
from app.services.flashcard_generator import generate_flashcards
from app.services.knowledge_extractor import extract_knowledge
from app.services.notes_generator import clean_notes, generate_notes, render_markdown
from app.services.quiz_generator import generate_quiz
from app.services.summarization_service import compress_digests, summarize_lecture

CHUNKS = [{"idx": i, "start": i * 60.0, "end": i * 60.0 + 60, "seg_start": i, "seg_end": i, "text": f"Part {i} speech recognition text"}
          for i in range(5)]
SEGS = [{"idx": i, "start": i * 60.0, "end": i * 60.0 + 60, "text": "The acoustic model and speech recognition"} for i in range(5)]
META = {"title": "ASR 101", "subject": "Speech"}


async def test_summary_is_map_reduce_not_one_giant_prompt(fake_llm):
    out = await summarize_lecture(CHUNKS, META)
    names = [n for n, _ in fake_llm.calls]
    assert names.count("ChunkDigest") == len(CHUNKS)  # one map call per chunk
    assert names[-1] == "LectureSummary"
    # each map prompt contains only its own chunk
    for (_, prompt), ch in zip(fake_llm.calls, CHUNKS):
        assert ch["text"] in prompt
        assert all(o["text"] not in prompt for o in CHUNKS if o is not ch)
    assert len(out["summary"]["quick_summary"]) == 5  # validator trims to five lines
    assert out["chapters"][0]["start"] == 0.0
    assert [d["chunk_index"] for d in out["digests"]] == [0, 1, 2, 3, 4]


async def test_compress_digests_hierarchical(fake_llm):
    big = [{**ChunkDigest(title=f"T{i}", summary="x" * 3000).model_dump(), "chunk_index": i, "start": i, "end": i + 1}
           for i in range(12)]
    reduced = await compress_digests(big, META, budget=8000)
    assert len(reduced) < len(big)
    assert [n for n, _ in fake_llm.calls].count("ChunkDigest") >= 1


async def test_notes_generation_and_markdown(fake_llm):
    digests = (await summarize_lecture(CHUNKS, META))["digests"]
    notes = clean_notes((await generate_notes(digests, META, "exam")).model_dump())
    assert notes["title"] == "ASR 101"
    assert notes["sections"][0]["bullets"] == ["Maps audio to phonemes"]  # stray bullet removed
    md = render_markdown(notes, {0: 0.0})
    assert md.startswith("# ASR 101")
    assert "## Acoustic model" in md and "**ASR**" in md and "Final revision summary" in md


async def test_quiz_normalisation(fake_llm):
    quiz = await generate_quiz([{"chunk_index": 0, "start": 0, "end": 1, "title": "t", "summary": "s"}], META)
    qs = quiz["questions"]
    types = [q["type"] for q in qs]
    assert types.count("mcq") == 1  # the 2-option MCQ was dropped
    mcq = next(q for q in qs if q["type"] == "mcq")
    assert len(mcq["options"]) == 4 and mcq["correct_answer"] == "Speech recognition"
    assert mcq["correct_answer"] in mcq["options"] and all(not o.startswith("A)") for o in mcq["options"])
    tf = next(q for q in qs if q["type"] == "true_false")
    assert tf["correct_answer"] == "False" and tf["options"] == ["True", "False"]
    assert all(q["id"] for q in qs)


async def test_flashcards_dedupe(fake_llm):
    cards = await generate_flashcards([{"chunk_index": 0, "start": 0, "end": 1, "title": "t", "summary": "s"}], META)
    assert [c["front"] for c in cards] == ["ASR?"]
    assert cards[0]["review_count"] == 0 and cards[0]["rating"] is None


async def test_knowledge_map_sanitised(fake_llm):
    km = await extract_knowledge([{"chunk_index": 0, "start": 0, "end": 60, "title": "t", "summary": "s"}], META, CHUNKS, SEGS)
    assert {n["id"] for n in km["nodes"]} == {"n1", "n2"}
    assert km["edges"] == [{"source": "n1", "target": "n2", "relation": "uses"}]  # edge to unknown node dropped
    assert km["nodes"][1]["timestamp"] == 0.0


class _Msg:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})()


class _RawChat:
    """Fake OpenAI client: first answer is invalid JSON, second is valid."""
    def __init__(self, contents):
        self.contents = list(contents)
        self.kwargs = []
        self.chat = type("C", (), {})()
        self.chat.completions = self

    async def create(self, **kw):
        self.kwargs.append(kw)
        return type("R", (), {"choices": [_Msg(self.contents.pop(0))]})()


async def test_llm_client_validates_and_retries(monkeypatch):
    from app.core import config
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config.get_settings.cache_clear()
    good = {"executive_summary": "x", "quick_summary": ["1"], "detailed_summary": []}
    raw = _RawChat(["not json at all", "```json\n" + json.dumps(good) + "\n```"])
    out = await llm_client.LLMClient(client=raw).chat_json("sys", "user", LectureSummary)
    assert out.executive_summary == "x"
    assert len(raw.kwargs) == 2
    assert raw.kwargs[0]["response_format"]["type"] == "json_schema"
    assert "That JSON was invalid" in raw.kwargs[1]["messages"][-1]["content"]


async def test_llm_unavailable_without_key(monkeypatch):
    from app.core import config
    monkeypatch.setenv("OPENAI_API_KEY", "")
    config.get_settings.cache_clear()
    with pytest.raises(llm_client.LLMUnavailable):
        llm_client.LLMClient().raw_client()
