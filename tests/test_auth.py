def test_signup_missing_fields_returns_400(client):
    r = client.post("/api/auth/signup", json={})
    assert r.status_code == 400
    assert r.get_json()["status"] == "error"


def test_signup_missing_email_returns_400(client):
    r = client.post("/api/auth/signup", json={"first_name": "Test", "password": "Abcd1234!"})
    assert r.status_code == 400


def test_signup_missing_password_returns_400(client):
    r = client.post("/api/auth/signup", json={"first_name": "Test", "email": "t@example.com"})
    assert r.status_code == 400


def test_login_missing_fields_returns_400(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code == 400
    assert r.get_json()["status"] == "error"


def test_login_missing_password_returns_400(client):
    r = client.post("/api/auth/login", json={"email": "x@example.com"})
    assert r.status_code == 400


def test_profile_without_token_returns_4xx(client):
    r = client.get("/api/auth/profile")
    # Profile route exists; without a token it should reject (any 4xx is acceptable)
    assert 400 <= r.status_code < 500


def test_progress_without_token_returns_4xx(client):
    r = client.get("/api/auth/progress")
    assert 400 <= r.status_code < 500


def test_google_auth_missing_credential_returns_4xx(client):
    r = client.post("/api/auth/google", json={})
    assert 400 <= r.status_code < 500


def test_cors_preflight_on_auth_google(client):
    r = client.options(
        "/api/auth/google",
        headers={
            "Origin": "https://learnexusfrontend.vercel.app",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code in (200, 204)
    assert "Access-Control-Allow-Origin" in r.headers
