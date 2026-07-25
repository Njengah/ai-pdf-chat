from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.config import Settings, get_settings
from backend.models.store import MemoryStore, UserRecord

_security = HTTPBearer(auto_error=False)
_store: Optional[MemoryStore] = None


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> MemoryStore:
    global _store
    if _store is None:
        from backend.seed import seed_demo_user

        _store = MemoryStore(settings.vector_store_path)
        seed_demo_user(_store)
    return _store


def create_access_token(user_id: str, settings: Settings) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.app_secret,
        algorithm="HS256",
    )


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_security)],
    settings: Annotated[Settings, Depends(get_settings)],
    store: Annotated[MemoryStore, Depends(get_store)],
) -> UserRecord:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, settings.app_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = store.get_user(UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
