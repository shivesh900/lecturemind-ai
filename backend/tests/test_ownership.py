"""Users must never see or modify another user's lectures."""
from .helpers import seed_lecture, user_id


async def test_other_user_gets_404_everywhere(client, db, alice, bob):
    lid, qid = await seed_lecture(db, await user_id(client, alice))
    L = f"/api/lectures/{lid}"
    gets = ["", "/status", "/transcript", "/transcript/search?q=Fourier", "/summary", "/notes", "/knowledge-map", "/quizzes",
            "/flashcards", "/chat", "/media", "/export/transcript", "/export/summary", "/export/notes", "/export/quiz",
            "/export/flashcards", "/export/json"]
    for p in gets:
        assert (await client.get(L + p, headers=alice)).status_code != 404 or p == "/media", p
        r = await client.get(L + p, headers=bob)
        assert r.status_code == 404, p
    writes = [("patch", "", {"title": "hacked"}), ("delete", "", None), ("post", "/reprocess", None),
              ("patch", "/transcript", {"segments": [{"idx": 0, "text": "hacked"}]}), ("patch", "/notes", {"markdown": "x"}),
              ("post", "/chat", {"message": "hi"}), ("post", "/quiz", {}), ("post", "/flashcards", None),
              ("post", "/flashcards/c1/review", {"rating": "easy"}), ("post", "/summary", None), ("delete", "/chat", None)]
    for method, p, body in writes:
        kw = {"headers": bob}
        if body is not None:
            kw["json"] = body
        r = await getattr(client, method)(L + p, **kw) if method != "delete" else await client.delete(L + p, headers=bob)
        assert r.status_code == 404, (method, p, r.status_code)
    # quiz endpoints by quiz id
    assert (await client.get(f"/api/quizzes/{qid}", headers=bob)).status_code == 404
    assert (await client.post(f"/api/quizzes/{qid}/attempts", json={"answers": {}}, headers=bob)).status_code == 404
    # nothing changed
    lec = await db.lectures.find_one({"_id": lid})
    assert lec["title"] == "Signals and Systems"
    assert (await db.transcript_segments.find_one({"lecture_id": lid, "idx": 0}))["text"].startswith("The Fourier")


async def test_lists_and_search_are_scoped(client, db, alice, bob):
    await seed_lecture(db, await user_id(client, alice))
    r = await client.get("/api/lectures", headers=bob)
    assert r.json()["items"] == []
    r = await client.get("/api/search?q=Nyquist", headers=bob)
    assert r.json()["results"] == []
    r = await client.get("/api/search?q=Nyquist", headers=alice)
    kinds = {m["kind"] for g in r.json()["results"] for m in g["matches"]}
    assert {"transcript", "notes", "concept"} <= kinds
    stats = (await client.get("/api/dashboard/stats", headers=bob)).json()
    assert stats["total_lectures"] == 0


async def test_invalid_ids(client, alice):
    assert (await client.get("/api/lectures/not-an-id", headers=alice)).status_code == 404
    assert (await client.get("/api/lectures/507f1f77bcf86cd799439011", headers=alice)).status_code == 404
