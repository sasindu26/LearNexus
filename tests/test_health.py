def test_health_returns_200(client):
    r = client.get("/")
    assert r.status_code == 200


def test_health_payload_shape(client):
    r = client.get("/")
    data = r.get_json()
    assert data["status"] == "Server is running"
    assert "server_time" in data
    assert "python_version" in data
    assert data["cors_enabled"] is True


def test_unknown_route_returns_404(client):
    r = client.get("/this-route-does-not-exist")
    assert r.status_code == 404
    data = r.get_json()
    assert data["status"] == "error"
    assert data["code"] == 404
