from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from backend.config import Settings, get_settings
from backend.models.schemas import ChatMessage, ChatResponse, SourceChunk
from backend.models.store import ChunkRecord, SQLiteStore
from backend.services.embeddings import embed_texts, top_k_chunks
from backend.services.llm_providers import (
    ResolvedModel,
    chat_completion,
    resolve_model,
    stream_chat_completion,
)


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


def _resolve_chat_model(
    store: SQLiteStore,
    owner_id: UUID,
    settings: Settings,
    model_id: Optional[UUID] = None,
) -> tuple[Optional[ResolvedModel], Optional[UUID]]:
    chat_record = None
    used_model_id: Optional[UUID] = None
    if model_id:
        chat_record = store.get_model(model_id, owner_id)
        if chat_record is None or chat_record.kind != "chat":
            raise ValueError("Selected chat model not found")
        used_model_id = UUID(chat_record.id)
    else:
        chat_record = store.get_default_model(owner_id, "chat")
        if chat_record:
            used_model_id = UUID(chat_record.id)
    return resolve_model(chat_record, "chat", settings), used_model_id


def _demo_answer(question: str, context: str) -> str:
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


async def _call_llm(
    question: str,
    context: str,
    store: SQLiteStore,
    owner_id: UUID,
    settings: Settings,
    model_id: Optional[UUID] = None,
) -> tuple[str, Optional[UUID]]:
    model, used_model_id = _resolve_chat_model(store, owner_id, settings, model_id)
    if model is None or not model.api_key:
        return _demo_answer(question, context), used_model_id

    user_prompt = (
        f"Context from PDFs:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer using the context above."
    )
    answer = await chat_completion(model, SYSTEM_PROMPT, user_prompt)
    return answer, used_model_id


async def _retrieve_sources(
    store: SQLiteStore,
    owner_id: UUID,
    question: str,
    document_ids: Optional[list[UUID]],
    settings: Settings,
) -> list[SourceChunk]:
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
    return [
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


async def answer_question(
    store: SQLiteStore,
    owner_id: UUID,
    question: str,
    document_ids: Optional[list[UUID]] = None,
    session_id: Optional[UUID] = None,
    model_id: Optional[UUID] = None,
    settings: Optional[Settings] = None,
) -> ChatResponse:
    settings = settings or get_settings()
    session = store.get_or_create_session(owner_id, session_id)
    sources = await _retrieve_sources(store, owner_id, question, document_ids, settings)
    answer, used_model_id = await _call_llm(
        question,
        _build_context(sources),
        store,
        owner_id,
        settings,
        model_id=model_id,
    )

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
        title=refreshed.title,
        model_id=used_model_id,
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def stream_answer_question(
    store: SQLiteStore,
    owner_id: UUID,
    question: str,
    document_ids: Optional[list[UUID]] = None,
    session_id: Optional[UUID] = None,
    model_id: Optional[UUID] = None,
    settings: Optional[Settings] = None,
) -> AsyncIterator[str]:
    settings = settings or get_settings()
    try:
        session = store.get_or_create_session(owner_id, session_id)
        yield _sse("stage", {"stage": "retrieving", "label": "Retrieving passages"})

        sources = await _retrieve_sources(store, owner_id, question, document_ids, settings)
        yield _sse("stage", {"stage": "ranking", "label": "Ranking context"})
        await asyncio.sleep(0.05)
        yield _sse(
            "stage",
            {
                "stage": "generating",
                "label": "Generating answer",
                "source_count": len(sources),
            },
        )

        context = _build_context(sources)
        model, used_model_id = _resolve_chat_model(store, owner_id, settings, model_id)
        answer_parts: list[str] = []

        if model is None or not model.api_key:
            answer = _demo_answer(question, context)
            for i in range(0, len(answer), 24):
                piece = answer[i : i + 24]
                answer_parts.append(piece)
                yield _sse("token", {"text": piece})
                await asyncio.sleep(0.01)
        else:
            user_prompt = (
                f"Context from PDFs:\n{context}\n\n"
                f"Question: {question}\n\n"
                "Answer using the context above."
            )
            async for piece in stream_chat_completion(model, SYSTEM_PROMPT, user_prompt):
                answer_parts.append(piece)
                yield _sse("token", {"text": piece})

        answer = "".join(answer_parts).strip()
        yield _sse("sources", {"sources": [s.model_dump(mode="json") for s in sources]})

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
        yield _sse(
            "done",
            {
                "session_id": session.id,
                "title": refreshed.title,
                "model_id": str(used_model_id) if used_model_id else None,
                "answer": answer,
                "messages": [m.model_dump(mode="json") for m in messages],
            },
        )
    except Exception as exc:  # noqa: BLE001 - surface to SSE client
        yield _sse("error", {"detail": str(exc)})


def session_to_markdown(session) -> str:
    lines = [
        f"# {session.title}",
        "",
        f"_Session `{session.id}` · created {session.created_at}_",
        "",
    ]
    for msg in session.messages:
        role = "You" if msg.get("role") == "user" else "Assistant"
        lines.append(f"## {role}")
        lines.append("")
        lines.append(str(msg.get("content") or "").strip())
        lines.append("")
        sources = msg.get("sources") or []
        if sources:
            lines.append("### Sources")
            lines.append("")
            for src in sources:
                lines.append(
                    f"- **{src.get('filename')}** p.{src.get('page')} "
                    f"(score {src.get('score', 0)})"
                )
                text = str(src.get("text") or "")[:240]
                if text:
                    lines.append(f"  > {text}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


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
