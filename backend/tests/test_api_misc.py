from .helpers import seed_lecture, user_id


async def test_transcript_edit_and_search(client, db, alice):
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    r = await client.patch(f"/api/lectures/{lid}/transcript", json={"segments": [{"idx": 2, "text": "This is called the  Nyquist frequency."}]}, headers=alice)
    assert r.status_code == 200 and r.json()["updated"] == 1
    t = (await client.get(f"/api/lectures/{lid}/transcript", headers=alice)).json()
    assert t["segments"][2]["text"] == "This is called the Nyquist frequency." and t["segments"][2]["edited"]
    chunk = await db.transcript_chunks.find_one({"lecture_id": lid})
    assert "Nyquist frequency" in chunk["text"]  # chunk kept in sync for chat/search
    s = (await client.get(f"/api/lectures/{lid}/transcript/search?q=nyquist", headers=alice)).json()
    assert s["total"] == 1 and s["segments"][0]["idx"] == 2
    bad = await client.patch(f"/api/lectures/{lid}/transcript", json={"segments": [{"idx": 0, "text": "  "}]}, headers=alice)
    assert bad.status_code == 422


async def test_library_filters_and_update(client, db, alice):
    uid = await user_id(client, alice)
    lid, _ = await seed_lecture(db, uid, "B lecture")
    await seed_lecture(db, uid, "A lecture")
    items = (await client.get("/api/lectures?sort=title", headers=alice)).json()["items"]
    assert [i["title"] for i in items] == ["A lecture", "B lecture"]
    assert (await client.get("/api/lectures?q=zzz", headers=alice)).json()["items"] == []
    assert len((await client.get("/api/lectures?status=completed&subject=ECE", headers=alice)).json()["items"]) == 2
    r = await client.patch(f"/api/lectures/{lid}", json={"title": "Renamed", "subject": "Maths"}, headers=alice)
    assert r.json()["lecture"]["title"] == "Renamed"
    assert (await client.delete(f"/api/lectures/{lid}", headers=alice)).status_code == 200
    assert await db.transcript_segments.count_documents({"lecture_id": lid}) == 0


async def test_quiz_grading_and_flashcard_review(client, db, alice):
    lid, qid = await seed_lecture(db, await user_id(client, alice))
    r = await client.post(f"/api/quizzes/{qid}/attempts", json={"answers": {"q1": "2 fmax"}, "self_marks": {"q2": False}}, headers=alice)
    a = r.json()
    assert a["score"] == 50.0 and a["correct"] == 1 and a["gradable"] == 2
    r = await client.post(f"/api/lectures/{lid}/flashcards/c1/review", json={"rating": "hard"}, headers=alice)
    assert r.json()["card"]["rating"] == "hard" and r.json()["card"]["review_count"] == 1
    act = (await client.get("/api/dashboard/activity?days=7", headers=alice)).json()["days"]
    assert len(act) == 7 and act[-1]["quiz_attempts"] == 1 and act[-1]["flashcard_reviews"] == 1
    hist = (await client.get("/api/attempts", headers=alice)).json()["attempts"]
    assert hist[0]["lecture_title"] == "Signals and Systems"


async def test_user_data_deletion(client, db, alice):
    await seed_lecture(db, await user_id(client, alice))
    r = await client.delete("/api/users/me/data", headers=alice)
    assert r.status_code == 200 and await db.lectures.count_documents({}) == 0
    r = await client.request("DELETE", "/api/users/me", json={"password": "wrong"}, headers=alice)
    assert r.status_code == 400
    r = await client.request("DELETE", "/api/users/me", json={"password": "password123"}, headers=alice)
    assert r.status_code == 200 and await db.users.count_documents({}) == 0
