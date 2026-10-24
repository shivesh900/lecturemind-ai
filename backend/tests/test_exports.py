import io
import zipfile

from .helpers import seed_lecture, user_id


async def test_all_exports(client, db, alice):
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    L = f"/api/lectures/{lid}/export"

    r = await client.get(f"{L}/transcript?format=txt", headers=alice)
    assert r.status_code == 200 and "text/plain" in r.headers["content-type"]
    assert 'filename="signals-and-systems-transcript.txt"' in r.headers["content-disposition"]
    assert "[00:10] Sampling must happen" in r.text

    r = await client.get(f"{L}/transcript?format=srt", headers=alice)
    assert "00:00:10,000 --> 00:00:19,000" in r.text

    r = await client.get(f"{L}/transcript?format=docx", headers=alice)
    xml = zipfile.ZipFile(io.BytesIO(r.content)).read("word/document.xml").decode()
    assert "Nyquist rate" in xml

    for kind in ("summary", "notes"):
        r = await client.get(f"{L}/{kind}?format=pdf", headers=alice)
        assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 1500
        r = await client.get(f"{L}/{kind}?format=docx", headers=alice)
        assert "Nyquist" in zipfile.ZipFile(io.BytesIO(r.content)).read("word/document.xml").decode()
        r = await client.get(f"{L}/{kind}?format=md", headers=alice)
        assert "Nyquist" in r.text

    r = await client.get(f"{L}/notes?format=txt", headers=alice)
    assert "**" not in r.text and "Nyquist rate" in r.text

    r = await client.get(f"{L}/quiz?format=pdf", headers=alice)
    assert r.content.startswith(b"%PDF")
    r = await client.get(f"{L}/quiz?format=md", headers=alice)
    assert "Answer key" in r.text and "2 fmax" in r.text

    r = await client.get(f"{L}/flashcards", headers=alice)
    assert r.text.splitlines()[0] == "front,back,difficulty,your_rating,times_reviewed"
    assert "Nyquist rate?" in r.text

    r = await client.get(f"{L}/json", headers=alice)
    data = r.json()
    assert data["lecture"]["title"] == "Signals and Systems"
    assert len(data["transcript"]) == 3 and data["quizzes"][0]["questions"][0]["id"] == "q1"
    assert "user_id" not in data["lecture"]


async def test_export_missing_material(client, db, alice):
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    await db.study_notes.delete_many({})
    r = await client.get(f"/api/lectures/{lid}/export/notes?format=pdf", headers=alice)
    assert r.status_code == 404 and r.json()["error"]["message"] == "No notes yet."
    r = await client.get(f"/api/lectures/{lid}/export/notes?format=exe", headers=alice)
    assert r.status_code == 422
