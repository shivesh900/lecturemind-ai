"""Content safety: lexicon detector, AI-moderation merge (mocked), endpoints and ownership."""
import pytest

from app.core import config
from app.services import content_safety_service as cs

from .helpers import seed_lecture, user_id


def cats(text):
    return {(m.category, m.severity) for m in cs.scan_text(text)}


# ---------------------------------------------------------------- lexicon detector
def test_clean_sentence_has_no_flags():
    assert cs.scan_text("Today we derive the Fourier transform and the Nyquist sampling rate.") == []


@pytest.mark.parametrize("text", [
    "Please assess the class on Scunthorpe and Penistone examples.",
    "Pass the classic assignment to the assistant.",
    "Hello, open a shell and type the command.",
    "Sunni and Shia are branches of Islam.",
    "I'll beat your previous record in the exam.",
    "I'll find you a better reference book.",
])
def test_false_positive_guards(text):
    assert cs.scan_text(text) == []


def test_kill_the_process_in_technical_context_is_not_a_threat():
    ms = cs.scan_text("Use kill -9 to kill the process, then kill the child thread and restart the server.")
    assert not any(m.category == "threat" for m in ms)


def test_profanity_detected_with_span():
    text = "This proof is total shit."
    [m] = cs.scan_text(text)
    assert (m.category, m.severity) == ("profanity", "medium")
    assert text[m.start:m.end] == "shit"


@pytest.mark.parametrize("text,term", [("what the f*ck", "f*ck"), ("this is sh1t", "sh1t"), ("you b!tch", "b!tch"),
                                       ("FUUUCK", "FUUUCK"), ("f**king hell", "f**king")])
def test_leetspeak_and_masking(text, term):
    terms = [m.term for m in cs.scan_text(text)]
    assert term in terms


@pytest.mark.parametrize("text,sev", [
    ("I will kill you after class", "high"),
    ("I'm gonna beat you up tomorrow", "medium"),
    ("You're dead.", "high"),
    ("Better watch your back", "medium"),
    ("I know where you live", "high"),
])
def test_threat_patterns(text, sev):
    assert ("threat", sev) in cats(text)


def test_hinglish_and_tamil_english():
    assert ("threat", "high") in cats("tujhe jaan se maar dunga")
    assert ("insult", "high") in cats("abe chutiya")
    assert ("threat", "high") in cats("unna kolluven da")


def test_insult_and_hate_categories():
    c = {m.category for m in cs.scan_text("you stupid idiot, shut up")}
    assert c == {"insult"}
    assert ("hate", "high") in cats("he called him a retard")


def test_mask_term():
    assert cs.mask_term("fuck") == "f**k"
    assert cs.mask_term("idiot") == "i***t"


# ---------------------------------------------------------------- AI moderation merge (mocked)
class _Res:
    def __init__(self, cats, scores):
        self._d = {"flagged": any(cats.values()), "categories": cats, "category_scores": scores}

    def model_dump(self, by_alias=True):
        return self._d


class FakeModeration:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail
        outer = self

        class _M:
            async def create(self, model, input):
                outer.calls.append((model, list(input)))
                if outer.fail:
                    raise RuntimeError("moderation down")
                out = []
                for t in input:
                    if "hurt" in t:
                        out.append(_Res({"harassment/threatening": True, "violence": True},
                                        {"harassment/threatening": 0.91, "violence": 0.7}))
                    else:
                        out.append(_Res({}, {"harassment": 0.01}))
                return type("R", (), {"results": out})()
        self.moderations = _M()


@pytest.fixture
def ai_on(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("MODERATION_BATCH_SIZE", "2")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


async def test_moderation_merged_with_lexicon(ai_on):
    fake = FakeModeration()
    texts = ["Clean sentence about sampling.", "Someone could get hurt by this, idiot.", "Another clean one."]
    per, info = await cs.analyze_texts(texts, client=fake)
    assert info["status"] == "used" and info["model"] == "omni-moderation-latest"
    assert [len(b) for _, b in fake.calls] == [2, 1]  # batched
    assert per[0] == [] and per[2] == []
    sources = {(f["category"], f["source"]) for f in per[1]}
    assert ("insult", "lexicon") in sources and ("threat", "ai_moderation") in sources
    threat = next(f for f in per[1] if f["source"] == "ai_moderation")
    assert threat["severity"] == "high" and threat["score"] == 0.91


async def test_moderation_failure_keeps_lexicon(ai_on):
    per, info = await cs.analyze_texts(["you idiot"], client=FakeModeration(fail=True))
    assert info["status"] == "failed" and "moderation down" in info["error"]
    assert per[0][0]["source"] == "lexicon"


async def test_no_key_means_lexicon_only():
    per, info = await cs.analyze_texts(["you idiot"])
    assert info["status"] == "disabled"
    assert per[0][0]["category"] == "insult"


# ---------------------------------------------------------------- endpoints
async def _harsh_lecture(client, db, headers):
    lid, _ = await seed_lecture(db, await user_id(client, headers))
    await db.transcript_segments.update_one({"lecture_id": lid, "idx": 1},
                                            {"$set": {"text": "If you skip lab again I will kill you, you idiot."}})
    return lid


async def test_safety_report_and_ownership(client, db, alice, bob):
    lid = await _harsh_lecture(client, db, alice)
    r = await client.get(f"/api/lectures/{lid}/safety", headers=alice)
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]["total_flagged"] == 1
    assert body["summary"]["by_category"]["threat"] == 1 and body["summary"]["by_category"]["insult"] == 1
    f = body["flagged"][0]
    assert f["segment_idx"] == 1 and f["start"] == 10.0 and f["severity"] == "high"
    assert body["moderation"]["status"] == "disabled"
    assert await db.content_safety.count_documents({"lecture_id": lid}) == 1
    # another user can't see or rescan it
    assert (await client.get(f"/api/lectures/{lid}/safety", headers=bob)).status_code == 404
    assert (await client.post(f"/api/lectures/{lid}/safety/rescan", headers=bob)).status_code == 404


async def test_transcript_edit_rescans(client, db, alice):
    lid = await _harsh_lecture(client, db, alice)
    assert (await client.get(f"/api/lectures/{lid}/safety", headers=alice)).json()["summary"]["total_flagged"] == 1
    r = await client.patch(f"/api/lectures/{lid}/transcript", headers=alice,
                           json={"segments": [{"idx": 1, "text": "If you skip lab again you will lose marks."}]})
    assert r.status_code == 200
    assert (await client.get(f"/api/lectures/{lid}/safety", headers=alice)).json()["summary"]["total_flagged"] == 0
    r = await client.post(f"/api/lectures/{lid}/safety/rescan", headers=alice)
    assert r.status_code == 200 and r.json()["summary"]["total_flagged"] == 0


async def test_check_endpoint(client, alice, monkeypatch):
    r = await client.post("/api/safety/check", headers=alice, json={"text": "Watch your back, you b!tch"})
    body = r.json()
    assert r.status_code == 200 and body["flagged"] and body["severity"] == "high"
    assert set(body["categories"]) == {"threat", "insult"}
    assert body["matches"][0]["masked"]
    r = await client.post("/api/safety/check", headers=alice, json={"text": "The Nyquist rate is twice fmax."})
    assert r.json()["flagged"] is False
    client.cookies.clear()
    assert (await client.post("/api/safety/check", json={"text": "hi"})).status_code == 401
    monkeypatch.setenv("SAFETY_CHECK_RATE_LIMIT_PER_MINUTE", "2")
    config.get_settings.cache_clear()
    codes = [(await client.post("/api/safety/check", headers=alice, json={"text": "hello"})).status_code for _ in range(3)]
    assert codes[-1] == 429
