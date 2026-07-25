def _auth(client):
    return client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    ).json()["access_token"]


def test_chat_stream_emits_stages_tokens_and_done(client):
    token = _auth(client)
    with client.stream(
        "POST",
        "/api/chat/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Stream this answer please"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: stage" in body
    assert "retrieving" in body
    assert "ranking" in body
    assert "generating" in body
    assert "event: token" in body
    assert "event: sources" in body
    assert "event: done" in body
    assert "Stream this answer please" in body


def test_chat_stream_unknown_model_errors(client):
    token = _auth(client)
    with client.stream(
        "POST",
        "/api/chat/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "hello",
            "model_id": "00000000-0000-0000-0000-000000000099",
        },
    ) as response:
        body = "".join(response.iter_text())
    assert "event: error" in body
    assert "not found" in body.lower()
