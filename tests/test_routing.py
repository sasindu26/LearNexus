"""Smoke-test that every important blueprint is registered (no 404s on real routes)."""


def test_world_trending_route_registered(client):
    r = client.get("/api/world-trending?limit=1")
    assert r.status_code != 404


def test_courses_route_registered(client):
    r = client.get("/api/courses")
    assert r.status_code != 404


def test_modules_route_registered(client):
    r = client.get("/api/modules?course=Computer%20Science")
    assert r.status_code != 404


def test_career_dashboard_route_registered(client):
    r = client.get("/api/career/dashboard")
    assert r.status_code != 404


def test_login_route_registered(client):
    r = client.post("/api/auth/login", json={})
    assert r.status_code != 404


def test_signup_route_registered(client):
    r = client.post("/api/auth/signup", json={})
    assert r.status_code != 404


def test_google_auth_route_registered(client):
    r = client.post("/api/auth/google", json={})
    assert r.status_code != 404


def test_chat_route_registered(client):
    r = client.post("/chat", json={"message": ""})
    assert r.status_code != 404


def test_tech_recommendations_route_registered(client):
    r = client.get("/api/tech-recommendations/trending")
    assert r.status_code != 404
