def test_chat_empty_message_returns_400_or_503(client):
    """Empty message should be rejected (400); 503 acceptable if model not warm yet."""
    r = client.post("/chat", json={"message": "", "history": []})
    assert r.status_code in (400, 503)


def test_chat_missing_message_returns_400_or_503(client):
    r = client.post("/chat", json={"history": []})
    assert r.status_code in (400, 503)


def test_chat_get_returns_405(client):
    r = client.get("/chat")
    assert r.status_code == 405
