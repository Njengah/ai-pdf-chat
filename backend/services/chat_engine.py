from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from backend.config import Settings, get_settings
from backend.models.schemas import ChatMessage, ChatResponse, SourceChunk
from backend.models.store import ChunkRecord, SQLiteStore
from backend.services.embeddings import embed_texts, top_k_chunks
from backend.services.llm_providers import chat_completion, resolve_model


SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using only the provided "
    "PDF context. If the context is insufficient, say you do not know based on "
    "the uploaded documents. Cite page numbers when useful."
)


def _build_context(sources: list[SourceChunk]) -> str:
    blocks = []
    for idx, src in enumerate(sources, start=1):
        blocks.append(
            f"[{idx}] file={src.filename} page={src.page}\n{src.text}"
        )
    return "\n\n".join(blocks) if blocks else "(no relevant context found)"


async def _call_llm(question: str, context: str, store: SQLiteStore, owner_id: UUID, settings: Settings) -> str:
    chat_record = store.get_default_model(owner_id, "chat")
    model = resolve_model(chat_record, "chat", settings)

    if model is None or not model.api_key:
        if "(no relevant context found)" in context:
            return (
                "I could not find relevant passages in your uploaded PDFs. "
                "Upload a document or ask about something present in the file."
            )
        excerpt = context[:900]
        return (
            "(Local demo mode — add a chat model with API key in Settings → Models.)\n\n"
            f"Based on the retrieved context:\n{excerpt}\n\n"
            f"Question: {question}"
        )

    user_prompt = (
        f"Context from PDFs:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using the context above."
    )
    return await chat_completion(model, SYSTEM_PROMPT, user_prompt)


async def answer_question(
    store: SQLiteStore,
    owner_id: UUID,
    question: str,
    document_ids: Optional[list[UUID]] = None,
    session_id: Optional[UUID] = None,
    settings: Optional[Settings] = None,
) -> ChatResponse:
    settings = settings or get_settings()
    session = store.get_or_create_session(owner_id, session_id)

    embed_record = store.get_default_model(owner_id, "embedding")
    embed_model = resolve_model(embed_record, "embedding", settings)
    query_vecs = await embed_texts([question], settings=settings, model=embed_model)

    allowed = {str(d) for d in document_ids} if document_ids else None
    owner_docs = {d.id for d in store.list_documents(owner_id)}
    if allowed is None:
        allowed = owner_docs
    else:
        allowed = allowed & owner_docs

    ranked = top_k_chunks(
        query_vecs[0],
        store.list_chunks(allowed),
        k=settings.top_k,
        document_ids=allowed,
    )

    sources = [
        SourceChunk(
            document_id=UUID(chunk.document_id),
            filename=chunk.filename,
            page=chunk.page,
            text=chunk.text,
            score=round(score, 4),
        )
        for chunk, score in ranked
        if score > 0
    ]

    answer = await _call_llm(question, _build_context(sources), store, owner_id, settings)

    now = datetime.utcnow()
    user_msg = ChatMessage(role="user", content=question, created_at=now)
    assistant_msg = ChatMessage(
        role="assistant",
        content=answer,
        sources=sources,
        created_at=now,
    )

    refreshed = store.append_messages(
        session.id,
        [user_msg.model_dump(mode="json"), assistant_msg.model_dump(mode="json")],
    )
    messages = [ChatMessage(**m) for m in refreshed.messages]

    return ChatResponse(
        session_id=UUID(session.id),
        answer=answer,
        sources=sources,
        messages=messages,
    )


def make_chunk_records(
    document_id: str,
    filename: str,
    chunk_dicts: list[dict],
    embeddings: list[list[float]],
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for chunk, emb in zip(chunk_dicts, embeddings):
        records.append(
            ChunkRecord(
                id=str(uuid4()),
                document_id=document_id,
                filename=filename,
                page=chunk["page"],
                text=chunk["text"],
                embedding=emb,
            )
        )
    return records
