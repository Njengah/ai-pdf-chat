def _auth(client):
    return client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    ).json()["access_token"]


def test_create_list_and_mask_api_key(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/api/models",
        headers=headers,
        json={
            "name": "GPT Mini",
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "kind": "chat",
            "api_key": "sk-test-secret-key-1234",
            "is_default": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "GPT Mini"
    assert body["has_api_key"] is True
    assert body["api_key_masked"] != "sk-test-secret-key-1234"
    assert "sk-" in body["api_key_masked"] or "…" in body["api_key_masked"]
    assert "secret-key" not in body["api_key_masked"]

    listed = client.get("/api/models", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_anthropic_embedding_rejected(client):
    token = _auth(client)
    res = client.post(
        "/api/models",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Bad embed",
            "provider": "anthropic",
            "model_id": "claude-3-haiku",
            "kind": "embedding",
            "api_key": "ant-key",
        },
    )
    assert res.status_code == 400


def test_set_default_and_delete(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    a = client.post(
        "/api/models",
        headers=headers,
        json={
            "name": "Chat A",
            "provider": "openai",
            "model_id": "gpt-4o-mini",
            "kind": "chat",
            "api_key": "sk-aaa",
            "is_default": True,
        },
    ).json()
    b = client.post(
        "/api/models",
        headers=headers,
        json={
            "name": "Chat B",
            "provider": "anthropic",
            "model_id": "claude-sonnet-4-20250514",
            "kind": "chat",
            "api_key": "ant-bbb",
            "is_default": False,
        },
    ).json()

    switched = client.post(f"/api/models/{b['id']}/default", headers=headers)
    assert switched.status_code == 200
    assert switched.json()["is_default"] is True

    models = client.get("/api/models?kind=chat", headers=headers).json()
    defaults = [m for m in models if m["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == b["id"]

    assert client.delete(f"/api/models/{a['id']}", headers=headers).status_code == 204
    remaining = client.get("/api/models", headers=headers).json()
    assert len(remaining) == 1


def test_settings_status_models_ready(client):
    token = _auth(client)
    res = client.get(
        "/api/settings/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["sections"]["models"]["status"] == "ready"
    assert "count" in body["models"]
