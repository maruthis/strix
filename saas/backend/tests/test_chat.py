def test_suggestions(auth_client):
    client, _org = auth_client
    res = client.get("/api/chat/suggestions")
    assert res.status_code == 200
    body = res.json()
    assert "web" in body["categories"]
    assert len(body["suggestions"]["web"]) == 4


def test_session_and_message_flow(auth_client):
    client, _org = auth_client

    session = client.post("/api/chat/sessions", json={"category": "web"}).json()
    assert session["title"] == "New chat"

    sessions = client.get("/api/chat/sessions").json()
    assert len(sessions) == 1

    messages = client.post(f"/api/chat/sessions/{session['id']}/messages", json={"content": "Test API authorization"})
    assert messages.status_code == 200
    body = messages.json()
    assert len(body) == 2
    assert body[0]["role"] == "user"
    assert body[1]["role"] == "assistant"
    assert "web" in body[1]["content"]

    updated_session = client.get("/api/chat/sessions").json()[0]
    assert updated_session["title"] == "Test API authorization"

    history = client.get(f"/api/chat/sessions/{session['id']}/messages").json()
    assert len(history) == 2


def test_send_message_with_knowledge_context(auth_client):
    from .conftest import add_repo

    client, _org = auth_client
    repo = add_repo(client)
    client.post("/api/knowledge", json={"description": "Rate limit is 100 req/min.", "scope_type": "repository", "scope_id": repo["id"]})

    session = client.post("/api/chat/sessions", json={"category": "code"}).json()
    res = client.post(
        f"/api/chat/sessions/{session['id']}/messages",
        json={"content": "Audit the rate limiter", "repository_ids": [repo["id"]]},
    )
    reply = res.json()[1]["content"]
    assert "1 piece(s)" in reply


def test_send_message_empty_content_rejected(auth_client):
    client, _org = auth_client
    session = client.post("/api/chat/sessions", json={}).json()
    res = client.post(f"/api/chat/sessions/{session['id']}/messages", json={"content": "   "})
    assert res.status_code == 400
    assert res.json()["detail"] == "content_required"


def test_session_not_found(auth_client):
    client, _org = auth_client
    res = client.get("/api/chat/sessions/does-not-exist/messages")
    assert res.status_code == 404

    res = client.post("/api/chat/sessions/does-not-exist/messages", json={"content": "hi"})
    assert res.status_code == 404
