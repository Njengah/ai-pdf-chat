def test_settings_status_requires_auth(client):
    assert client.get("/api/settings/status").status_code == 401


def test_settings_status_reports_sqlite(client):
    token = client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    ).json()["access_token"]
    res = client.get(
        "/api/settings/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["storage"] == "sqlite"
    assert "models" in body["sections"]
    assert "appearance" in body["sections"]
    assert "danger" in body["sections"]
