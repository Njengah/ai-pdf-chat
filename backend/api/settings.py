from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.store import SQLiteStore, UserRecord

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/status")
def settings_status(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    models = store.list_models(user.id)
    chat_default = store.get_default_model(user.id, "chat")
    embed_default = store.get_default_model(user.id, "embedding")
    sessions = store.list_sessions(user.id)
    docs = store.list_documents(user.id)
    return {
        "storage": "sqlite",
        "database_path": str(settings.database_path),
        "upload_dir": str(settings.upload_dir),
        "sections": {
            "models": {
                "status": "ready",
                "note": "Manage OpenAI and Anthropic models. Keys stay server-side.",
            },
            "appearance": {
                "status": "ready",
                "note": "Light / dark theme preference (saved in this browser).",
            },
            "danger": {
                "status": "ready",
                "note": "Clear chats or wipe your PDF library.",
            },
        },
        "models": {
            "count": len(models),
            "default_chat": chat_default.name if chat_default else None,
            "default_embedding": embed_default.name if embed_default else None,
        },
        "workspace": {
            "session_count": len(sessions),
            "document_count": len(docs),
        },
        "demo": {
            "connected": store.get_user_by_email("demo@example.com") is not None,
        },
    }


@router.delete("/chats")
def clear_chats(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> dict[str, int]:
    deleted = store.clear_sessions(user.id)
    return {"deleted_sessions": deleted}


@router.delete("/library")
def clear_library(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> dict[str, int]:
    deleted = store.clear_library(user.id)
    return {"deleted_documents": deleted}
