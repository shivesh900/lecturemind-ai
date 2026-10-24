from bson import ObjectId

from app.models.documents import PIPELINE_STEPS, utcnow


async def user_id(client, headers):
    r = await client.get("/api/auth/me", headers=headers)
    return ObjectId(r.json()["user"]["id"])


async def seed_lecture(db, uid, title="Signals and Systems"):
    """Insert a fully processed lecture with every kind of material."""
    lid = ObjectId()
    now = utcnow()
    await db.lectures.insert_one({
        "_id": lid, "user_id": uid, "title": title, "subject": "ECE", "description": "Fourier series", "status": "completed",
        "progress": 100, "steps": {s: {"status": "completed", "error": None} for s in PIPELINE_STEPS}, "duration": 120.0,
        "kind": "audio", "media": {}, "mode": "ai", "created_at": now, "updated_at": now,
    })
    segs = [{"lecture_id": lid, "user_id": uid, "idx": i, "start": i * 10.0, "end": i * 10.0 + 9, "text": t, "speaker": None}
            for i, t in enumerate(["The Fourier transform decomposes a signal into frequencies.",
                                   "Sampling must happen at twice the highest frequency.",
                                   "This is called the Nyquist rate."])]
    await db.transcript_segments.insert_many(segs)
    await db.transcript_chunks.insert_one({"lecture_id": lid, "user_id": uid, "idx": 0, "start": 0.0, "end": 29.0,
                                           "seg_start": 0, "seg_end": 2, "text": " ".join(s["text"] for s in segs)})
    await db.summaries.insert_one({"lecture_id": lid, "user_id": uid, "mode": "ai", "chapters": [
        {"title": "Fourier", "start": 0.0, "end": 29.0, "summary": "Fourier and sampling", "chunk_index": 0}],
        "summary": {"executive_summary": "Fourier transform and the Nyquist rate.", "quick_summary": ["Fourier", "Nyquist"],
                    "detailed_summary": [{"heading": "Sampling", "content": "Sample at twice the max frequency."}],
                    "main_topics": [{"title": "Sampling", "description": "Nyquist"}], "arguments": [], "key_takeaways": ["Nyquist"],
                    "definitions": [{"term": "Nyquist rate", "definition": "Twice the highest frequency"}],
                    "formulas": [{"expression": "fs >= 2 fmax", "meaning": "sampling theorem"}], "examples": []},
        "digests": [{"chunk_index": 0, "start": 0.0, "end": 29.0, "title": "Fourier", "summary": "Fourier and Nyquist"}],
        "updated_at": now})
    await db.study_notes.insert_one({"lecture_id": lid, "user_id": uid, "markdown": "# Signals\n\n## Sampling\n- **Nyquist rate**: twice fmax\n- Use `fs >= 2 fmax`\n",
                                     "mode": "ai", "edited": False, "updated_at": now})
    q = await db.quizzes.insert_one({"lecture_id": lid, "user_id": uid, "title": "Quiz", "difficulty": "mixed", "source": "auto", "mode": "ai",
                                     "questions": [{"id": "q1", "type": "mcq", "question": "Nyquist rate is?", "options": ["fmax", "2 fmax", "3 fmax", "fmax/2"],
                                                    "correct_answer": "2 fmax", "explanation": "Twice", "difficulty": "easy", "important": True},
                                                   {"id": "q2", "type": "short", "question": "Define sampling.", "options": [],
                                                    "correct_answer": "Measuring a signal at intervals", "explanation": "", "difficulty": "medium", "important": False}],
                                     "created_at": now})
    await db.flashcards.insert_one({"lecture_id": lid, "user_id": uid, "mode": "ai", "updated_at": now, "cards": [
        {"id": "c1", "front": "Nyquist rate?", "back": "2 x fmax", "difficulty": "easy", "rating": None, "review_count": 0, "last_reviewed_at": None}]})
    await db.knowledge_maps.insert_one({"lecture_id": lid, "user_id": uid, "mode": "ai", "keywords": ["nyquist"],
                                        "nodes": [{"id": "n1", "label": "Nyquist rate", "type": "concept", "description": "2 fmax", "timestamp": 20.0}],
                                        "edges": []})
    return lid, q.inserted_id
