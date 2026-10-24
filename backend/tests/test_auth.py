from app.core.config import get_settings


async def test_register_login_me_logout(client, db):
    r = await client.post("/api/auth/register", json={"name": "Alice", "email": "Alice@Example.com", "password": "password123"})
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["email"] == "alice@example.com"
    assert "password_hash" not in body["user"]
    # cookie session is set and httpOnly
    set_cookie = r.headers["set-cookie"]
    assert get_settings().cookie_name in set_cookie and "httponly" in set_cookie.lower()

    # password is stored hashed (bcrypt), never in plain text
    user = await db.users.find_one({"email": "alice@example.com"})
    assert user["password_hash"].startswith("$2") and "password123" not in user["password_hash"]

    me = await client.get("/api/auth/me")  # uses the cookie
    assert me.status_code == 200 and me.json()["user"]["name"] == "Alice"

    out = await client.post("/api/auth/logout")
    assert out.status_code == 200
    client.cookies.clear()
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_login_and_bearer(client):
    await client.post("/api/auth/register", json={"name": "A", "email": "a@x.io", "password": "password123"})
    client.cookies.clear()
    bad = await client.post("/api/auth/login", json={"email": "a@x.io", "password": "wrong-pass1"})
    assert bad.status_code == 401
    assert bad.json()["error"]["message"] == "Incorrect email or password."
    ok = await client.post("/api/auth/login", json={"email": "a@x.io", "password": "password123"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    client.cookies.clear()
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


async def test_duplicate_and_validation(client):
    payload = {"name": "A", "email": "dup@x.io", "password": "password123"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    assert (await client.post("/api/auth/register", json=payload)).status_code == 409
    weak = await client.post("/api/auth/register", json={"name": "A", "email": "w@x.io", "password": "12345678"})
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "validation_error"
    bad_email = await client.post("/api/auth/register", json={"name": "A", "email": "nope", "password": "password123"})
    assert bad_email.status_code == 422


async def test_protected_routes_need_auth(client):
    for path in ["/api/lectures", "/api/dashboard/stats", "/api/search?q=test", "/api/attempts"]:
        r = await client.get(path)
        assert r.status_code == 401, path
    r = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


async def test_logout_all_devices_invalidates_tokens(client, alice):
    r = await client.post("/api/auth/logout?all_devices=true", headers=alice)
    assert r.status_code == 200
    client.cookies.clear()
    assert (await client.get("/api/auth/me", headers=alice)).status_code == 401


async def test_status_endpoint_never_exposes_secrets(client, monkeypatch):
    from app.core import config
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-123456789")
    config.get_settings.cache_clear()
    r = await client.get("/api/system/status")
    assert r.status_code == 200
    assert "sk-secret" not in r.text
    assert r.json()["ai_enabled"] is True
