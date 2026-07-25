def _auth(client):
    return client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    ).json()["access_token"]


def test_clear_chats(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/chat", headers=headers, json={"question": "hello world"})
    assert len(client.get("/api/chat/sessions", headers=headers).json()) >= 1

    cleared = client.delete("/api/settings/chats", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted_sessions"] >= 1
    assert client.get("/api/chat/sessions", headers=headers).json() == []


def test_clear_library(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    from datetime import datetime
    from uuid import uuid4
    from pathlib import Path

    from backend.api import deps
    from backend.config import get_settings
    from backend.models.store import ChunkRecord, DocumentRecord
    from backend.services.embeddings import _hash_embed

    store = deps._store
    assert store is not None
    user = store.authenticate("demo@example.com", "demo1234")
    assert user is not None
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid4())
    dest = Path(settings.upload_dir) / f"{doc_id}.pdf"
    dest.write_bytes(b"%PDF-1.4 demo")
    store.add_document(
        DocumentRecord(
            id=doc_id,
            filename="wipe.pdf",
            path=str(dest),
            page_count=1,
            chunk_count=1,
            uploaded_at=datetime.utcnow().isoformat(),
            owner_id=user.id,
        ),
        [
            ChunkRecord(
                id=str(uuid4()),
                document_id=doc_id,
                filename="wipe.pdf",
                page=1,
                text="wipe me",
                embedding=_hash_embed("wipe me"),
            )
        ],
    )
    assert len(client.get("/api/documents", headers=headers).json()) >= 1

    cleared = client.delete("/api/settings/library", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["deleted_documents"] >= 1
    assert client.get("/api/documents", headers=headers).json() == []


def test_settings_sections_ready(client):
    token = _auth(client)
    res = client.get(
        "/api/settings/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["sections"]["appearance"]["status"] == "ready"
    assert body["sections"]["danger"]["status"] == "ready"
    assert "workspace" in body
