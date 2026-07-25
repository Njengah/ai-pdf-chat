from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from backend.api.deps import get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatSessionRename,
    ChatSessionSummary,
)
from backend.models.store import SQLiteStore, UserRecord
from backend.services.chat_engine import answer_question, session_to_markdown

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


@router.get("/sessions", response_model=list[ChatSessionSummary])
def list_sessions(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> list[ChatSessionSummary]:
    return [
        ChatSessionSummary(
            id=UUID(s.id),
            owner_id=UUID(s.owner_id),
            title=s.title,
            created_at=_parse_dt(s.created_at),
            updated_at=_parse_dt(s.updated_at),
            message_count=s.message_count,
            preview=s.preview,
        )
        for s in store.list_sessions(user.id)
    ]


@router.patch("/sessions/{session_id}", response_model=ChatSessionSummary)
def rename_session(
    session_id: UUID,
    body: ChatSessionRename,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> ChatSessionSummary:
    session = store.rename_session(session_id, user.id, body.title)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    summaries = {s.id: s for s in store.list_sessions(user.id)}
    summary = summaries.get(session.id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return ChatSessionSummary(
        id=UUID(summary.id),
        owner_id=UUID(summary.owner_id),
        title=summary.title,
        created_at=_parse_dt(summary.created_at),
        updated_at=_parse_dt(summary.updated_at),
        message_count=summary.message_count,
        preview=summary.preview,
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> None:
    if not store.delete_session(session_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


@router.get("/sessions/{session_id}/export", response_class=PlainTextResponse)
def export_session(
    session_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> str:
    session = store.get_session(session_id)
    if not session or session.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session_to_markdown(session)


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    try:
        return await answer_question(
            store=store,
            owner_id=UUID(user.id),
            question=body.question,
            document_ids=body.document_ids,
            session_id=body.session_id,
            model_id=body.model_id,
            settings=settings,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=ChatSession)
def get_session(
    session_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> ChatSession:
    session = store.get_session(session_id)
    if not session or session.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return ChatSession(
        id=UUID(session.id),
        owner_id=UUID(session.owner_id),
        title=session.title,
        messages=[ChatMessage(**m) for m in session.messages],
        created_at=_parse_dt(session.created_at),
    )
