from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.schemas import ChatMessage, ChatRequest, ChatResponse, ChatSession
from backend.models.store import SQLiteStore, UserRecord
from backend.services.chat_engine import answer_question

router = APIRouter(prefix="/api/chat", tags=["chat"])


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
            settings=settings,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=ChatSession)
def get_session(
    session_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> ChatSession:
    session = store.get_session(session_id)
    if not session or session.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    created = (
        session.created_at
        if isinstance(session.created_at, datetime)
        else datetime.fromisoformat(str(session.created_at))
    )
    return ChatSession(
        id=UUID(session.id),
        owner_id=UUID(session.owner_id),
        messages=[ChatMessage(**m) for m in session.messages],
        created_at=created,
    )
