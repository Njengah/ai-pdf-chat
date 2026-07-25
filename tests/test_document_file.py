from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)

from backend.api import deps
from backend.config import get_settings
from backend.models.store import ChunkRecord, DocumentRecord
from backend.services.embeddings import _hash_embed


def _auth(client):
    return client.post(
        "/api/auth/login",
        json={"email": "demo@example.com", "password": "demo1234"},
    ).json()["access_token"]


def _pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject()
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 50 250 Td ({safe}) Tj ET".encode("latin-1", errors="ignore"))
    page[NameObject("/Contents")] = stream
    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject()
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources
    page.mediabox.lower_left = (NumberObject(0), NumberObject(0))
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_get_document_file(client):
    token = _auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    store = deps._store
    assert store is not None
    user = store.authenticate("demo@example.com", "demo1234")
    assert user is not None

    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid4())
    dest = Path(settings.upload_dir) / f"{doc_id}.pdf"
    dest.write_bytes(_pdf_bytes("Viewer file endpoint content."))
    text = "Viewer file endpoint content."
    store.add_document(
        DocumentRecord(
            id=doc_id,
            filename="viewer.pdf",
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
                filename="viewer.pdf",
                page=1,
                text=text,
                embedding=_hash_embed(text),
            )
        ],
    )

    file_res = client.get(f"/api/documents/{doc_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert file_res.headers["content-type"].startswith("application/pdf")
    assert file_res.content[:4] == b"%PDF"


def test_get_document_file_requires_auth(client):
    assert client.get("/api/documents/00000000-0000-0000-0000-000000000001/file").status_code == 401
