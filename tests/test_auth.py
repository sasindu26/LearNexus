def test_signup_missing_fields_returns_400(client):
    r = client.post("/signup", json={})
    assert r.status_code == 400
    assert r.get_json()["status"] == "error"


def test_signup_missing_email_returns_400(client):
    r = client.post("/signup", json={"first_name": "Test", "password": "Abcd1234!"})
    assert r.status_code == 400


def test_signup_missing_password_returns_400(client):
    r = client.post("/signup", json={"first_name": "Test", "email": "t@example.com"})
    assert r.status_code == 400


def test_login_missing_fields_returns_400(client):
    r = client.post("/login", json={})
    assert r.status_code == 400
    assert r.get_json()["status"] == "error"


def test_login_missing_password_returns_400(client):
    r = client.post("/login", json={"email": "x@example.com"})
    assert r.status_code == 400


def test_profile_without_token_returns_401(client):
    r = client.get("/profile")
    assert r.status_code in (401, 403)


def test_progress_without_token_returns_401(client):
    r = client.get("/progress")
    assert r.status_code in (401, 403)


def test_google_auth_missing_credential_returns_400(client):
    r = client.post("/google", json={})
    assert r.status_code in (400, 401)


def test_cors_preflight_on_auth_google(client):
    r = client.options(
        "/google",
        headers={
            "Origin": "https://learnexusfrontend.vercel.app",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code in (200, 204)
    assert "Access-Control-Allow-Origin" in r.headers
