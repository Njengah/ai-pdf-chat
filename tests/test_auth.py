def test_register_and_login(client):
    reg = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret12"},
    )
    assert reg.status_code == 201
    assert "access_token" in reg.json()

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {reg.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    login = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "secret12"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_seeded_demo_user_can_login(client):
    login = client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_duplicate_register_fails(client):
    payload = {"email": "dup@example.com", "password": "secret12"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    again = client.post("/api/auth/register", json=payload)
    assert again.status_code == 400
