from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.deps import get_current_user, get_store
from backend.config import Settings, get_settings
from backend.models.schemas import LLMModelCreate, LLMModelPublic, LLMModelUpdate
from backend.models.store import LLMModelRecord, SQLiteStore, UserRecord
from backend.services.crypto import decrypt_secret, encrypt_secret, mask_secret

router = APIRouter(prefix="/api/models", tags=["models"])


def _validate_combo(provider: str, kind: str) -> None:
    if kind == "embedding" and provider != "openai":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding models currently support OpenAI only",
        )


def _to_public(record: LLMModelRecord, settings: Settings) -> LLMModelPublic:
    plaintext = ""
    if record.api_key_encrypted:
        try:
            plaintext = decrypt_secret(record.api_key_encrypted, settings.app_secret)
        except ValueError:
            plaintext = ""
    return LLMModelPublic(
        id=UUID(record.id),
        name=record.name,
        provider=record.provider,
        model_id=record.model_id,
        kind=record.kind,
        base_url=record.base_url,
        api_key_masked=mask_secret(plaintext),
        has_api_key=bool(plaintext),
        is_default=record.is_default,
        created_at=datetime.fromisoformat(record.created_at),
        updated_at=datetime.fromisoformat(record.updated_at),
    )


@router.get("", response_model=list[LLMModelPublic])
def list_models(
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    kind: Optional[str] = Query(default=None, pattern="^(chat|embedding)$"),
) -> list[LLMModelPublic]:
    return [_to_public(m, settings) for m in store.list_models(user.id, kind=kind)]


@router.post("", response_model=LLMModelPublic, status_code=status.HTTP_201_CREATED)
def create_model(
    body: LLMModelCreate,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMModelPublic:
    _validate_combo(body.provider, body.kind)
    now = datetime.utcnow().isoformat()
    record = LLMModelRecord(
        id=str(uuid4()),
        name=body.name.strip(),
        provider=body.provider,
        model_id=body.model_id.strip(),
        kind=body.kind,
        base_url=(body.base_url or None),
        api_key_encrypted=encrypt_secret(body.api_key.strip(), settings.app_secret),
        is_default=body.is_default,
        owner_id=user.id,
        created_at=now,
        updated_at=now,
    )
    # First model of a kind becomes default automatically
    if not body.is_default and not store.get_default_model(user.id, body.kind):
        record.is_default = True
    store.create_model(record)
    return _to_public(record, settings)


@router.patch("/{model_id}", response_model=LLMModelPublic)
def update_model(
    model_id: UUID,
    body: LLMModelUpdate,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMModelPublic:
    existing = store.get_model(model_id, user.id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    provider = body.provider or existing.provider
    kind = body.kind or existing.kind
    _validate_combo(provider, kind)

    api_key_encrypted = existing.api_key_encrypted
    if body.api_key is not None and body.api_key.strip():
        api_key_encrypted = encrypt_secret(body.api_key.strip(), settings.app_secret)

    updated = LLMModelRecord(
        id=existing.id,
        name=(body.name.strip() if body.name else existing.name),
        provider=provider,
        model_id=(body.model_id.strip() if body.model_id else existing.model_id),
        kind=kind,
        base_url=existing.base_url if body.base_url is None else (body.base_url or None),
        api_key_encrypted=api_key_encrypted,
        is_default=existing.is_default if body.is_default is None else body.is_default,
        owner_id=existing.owner_id,
        created_at=existing.created_at,
        updated_at=datetime.utcnow().isoformat(),
    )
    store.update_model(updated)
    refreshed = store.get_model(model_id, user.id)
    assert refreshed is not None
    return _to_public(refreshed, settings)


@router.post("/{model_id}/default", response_model=LLMModelPublic)
def set_default_model(
    model_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMModelPublic:
    model = store.set_default_model(model_id, user.id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return _to_public(model, settings)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: UUID,
    user: Annotated[UserRecord, Depends(get_current_user)],
    store: Annotated[SQLiteStore, Depends(get_store)],
) -> None:
    if not store.delete_model(model_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
