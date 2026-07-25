def _auth(client):
    return client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    ).json()["access_token"]


def test_chat_history_rename_export_delete(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    chat = client.post(
        "/api/chat",
        headers=headers,
        json={"question": "What is in the documents?"},
    )
    assert chat.status_code == 200
    body = chat.json()
    session_id = body["session_id"]
    assert body["title"]
    assert len(body["messages"]) >= 2

    listed = client.get("/api/chat/sessions", headers=headers)
    assert listed.status_code == 200
    assert any(s["id"] == session_id for s in listed.json())

    renamed = client.patch(
        f"/api/chat/sessions/{session_id}",
        headers=headers,
        json={"title": "Research notes"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Research notes"

    exported = client.get(f"/api/chat/sessions/{session_id}/export", headers=headers)
    assert exported.status_code == 200
    assert "Research notes" in exported.text
    assert "What is in the documents?" in exported.text

    detailed = client.get(f"/api/chat/{session_id}", headers=headers)
    assert detailed.status_code == 200
    assert detailed.json()["title"] == "Research notes"

    assert client.delete(f"/api/chat/sessions/{session_id}", headers=headers).status_code == 204
    assert client.get("/api/chat/sessions", headers=headers).json() == []


def test_chat_rejects_unknown_model(client):
    token = _auth(client)
    res = client.post(
        "/api/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "question": "hello",
            "model_id": "00000000-0000-0000-0000-000000000099",
        },
    )
    assert res.status_code == 400
