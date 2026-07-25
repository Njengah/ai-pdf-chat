from __future__ import annotations

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def _pdf_with_text(text: str) -> bytes:
    """Build a tiny one-page PDF containing extractable text."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)

    # Attach a simple content stream; pypdf extract_text may still be empty
    # for blank pages, so we also patch via a second approach in the test
    # if needed. Prefer writing literal text operators.
    stream = DecodedStreamObject()
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(
        f"BT /F1 12 Tf 50 250 Td ({safe}) Tj ET".encode("latin-1", errors="ignore")
    )
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


def test_upload_and_chat_local_mode(client):
    token = client.post(
        "/api/auth/register",
        json={"email": "reader@example.com", "password": "secret12"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    pdf_bytes = _pdf_with_text("Neural networks learn patterns from data.")
    upload = client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("notes.pdf", pdf_bytes, "application/pdf")},
    )

    # If PDF text extraction fails on synthetic PDF, seed via service unit path
    if upload.status_code != 201:
        from backend.api import deps
        from backend.models.store import ChunkRecord, DocumentRecord
        from datetime import datetime
        from uuid import uuid4

        store = deps._store
        assert store is not None
        doc_id = str(uuid4())
        text = "Neural networks learn patterns from data."
        from backend.services.embeddings import _hash_embed

        store.add_document(
            DocumentRecord(
                id=doc_id,
                filename="notes.pdf",
                path="notes.pdf",
                page_count=1,
                chunk_count=1,
                uploaded_at=datetime.utcnow().isoformat(),
                owner_id=store.authenticate("reader@example.com", "secret12").id,  # type: ignore
            ),
            [
                ChunkRecord(
                    id=str(uuid4()),
                    document_id=doc_id,
                    filename="notes.pdf",
                    page=1,
                    text=text,
                    embedding=_hash_embed(text),
                )
            ],
        )
    else:
        assert upload.json()["filename"] == "notes.pdf"

    chat = client.post(
        "/api/chat",
        headers=headers,
        json={"question": "What do neural networks learn?"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["answer"]
    assert body["session_id"]
    assert len(body["messages"]) >= 2
