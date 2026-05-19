"""Smoke-test that every important blueprint is registered."""


def test_world_trending_route_registered(client):
    r = client.get("/api/world-trending?limit=1")
    # The route exists — accept 200 (DB up) or 500 (DB down in CI), but NOT 404
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
    r = client.post("/login", json={})
    assert r.status_code != 404


def test_signup_route_registered(client):
    r = client.post("/signup", json={})
    assert r.status_code != 404


def test_chat_route_registered(client):
    r = client.post("/chat", json={"message": ""})
    assert r.status_code != 404
