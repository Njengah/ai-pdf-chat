from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.store import SQLiteStore, UserRecord

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/status")
def settings_status(
    _user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """PR1 shell: storage info only. Models arrive in PR2."""
    return {
        "storage": "sqlite",
        "database_path": str(settings.database_path),
        "upload_dir": str(settings.upload_dir),
        "sections": {
            "models": {"status": "coming_soon", "note": "Configure OpenAI & Anthropic models in PR2"},
            "appearance": {"status": "coming_soon", "note": "Theme controls arrive in PR6"},
            "danger": {"status": "coming_soon", "note": "Reset actions arrive in PR6"},
        },
        "demo": {
            "connected": store.get_user_by_email("demo@example.com") is not None,
        },
    }
