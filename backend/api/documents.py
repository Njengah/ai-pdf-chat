from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from backend.api.deps import get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.schemas import DocumentMeta
from backend.models.store import DocumentRecord, SQLiteStore, UserRecord
from backend.services.chat_engine import make_chunk_records
from backend.services.embeddings import chunk_pages, embed_texts
from backend.services.llm_providers import resolve_model
from backend.services.pdf_parser import extract_text_from_pdf, page_count

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _meta(doc: DocumentRecord) -> DocumentMeta:
    return DocumentMeta(
        id=UUID(doc.id),
        filename=doc.filename,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        uploaded_at=datetime.fromisoformat(doc.uploaded_at),
        owner_id=UUID(doc.owner_id),
    )


@router.get("", response_model=list[DocumentMeta])
def list_documents(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> list[DocumentMeta]:
    return [_meta(d) for d in store.list_documents(user.id)]


@router.post("/upload", response_model=DocumentMeta, status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    file: UploadFile = File(...),
) -> DocumentMeta:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    doc_id = uuid4()
    dest = settings.upload_dir / f"{doc_id}.pdf"
    dest.write_bytes(raw)

    try:
        pages = extract_text_from_pdf(raw)
        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            dest.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No extractable text found in PDF",
            )
        embed_record = store.get_default_model(user.id, "embedding")
        embed_model = resolve_model(embed_record, "embedding", settings)
        embeddings = await embed_texts(
            [c["text"] for c in chunks],
            settings=settings,
            model=embed_model,
        )
        records = make_chunk_records(str(doc_id), file.filename, chunks, embeddings)
        doc = DocumentRecord(
            id=str(doc_id),
            filename=file.filename,
            path=str(dest),
            page_count=page_count(raw),
            chunk_count=len(records),
            uploaded_at=datetime.utcnow().isoformat(),
            owner_id=user.id,
        )
        store.add_document(doc, records)
        return _meta(doc)
    except HTTPException:
        raise
    except Exception as exc:
        Path(dest).unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/{document_id}/file")
def get_document_file(
    document_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> FileResponse:
    doc = store.get_document(document_id, user.id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    path = Path(doc.path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file missing on disk")
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=doc.filename,
        content_disposition_type="inline",
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> None:
    if not store.delete_document(document_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
