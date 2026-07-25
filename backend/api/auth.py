from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.deps import create_access_token, get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.schemas import TokenResponse, UserCreate, UserLogin, UserPublic
from backend.models.store import SQLiteStore, UserRecord

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_public(user: UserRecord) -> UserPublic:
    return UserPublic(
        id=UUID(user.id),
        email=user.email,
        created_at=datetime.fromisoformat(user.created_at),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    body: UserCreate,
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        user = store.create_user(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    token = create_access_token(user.id, settings)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    body: UserLogin,
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = store.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(user.id, settings))


@router.get("/me", response_model=UserPublic)
def me(user: Annotated[UserRecord, Depends(get_current_user)]) -> UserPublic:
    return _to_public(user)
