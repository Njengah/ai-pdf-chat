from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentMeta(BaseModel):
    id: UUID
    filename: str
    page_count: int
    chunk_count: int
    uploaded_at: datetime
    owner_id: UUID


class SourceChunk(BaseModel):
    document_id: UUID
    filename: str
    page: int
    text: str
    score: float


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: list[SourceChunk] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    document_ids: Optional[list[UUID]] = None
    session_id: Optional[UUID] = None


class ChatResponse(BaseModel):
    session_id: UUID
    answer: str
    sources: list[SourceChunk]
    messages: list[ChatMessage]


class ChatSession(BaseModel):
    id: UUID
    owner_id: UUID
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(pattern="^(openai|anthropic)$")
    model_id: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(chat|embedding)$")
    base_url: Optional[str] = None
    api_key: str = Field(default="", max_length=500)
    is_default: bool = False


class LLMModelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    provider: Optional[str] = Field(default=None, pattern="^(openai|anthropic)$")
    model_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    kind: Optional[str] = Field(default=None, pattern="^(chat|embedding)$")
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(default=None, max_length=500)
    is_default: Optional[bool] = None


class LLMModelPublic(BaseModel):
    id: UUID
    name: str
    provider: str
    model_id: str
    kind: str
    base_url: Optional[str] = None
    api_key_masked: str = ""
    has_api_key: bool = False
    is_default: bool = False
    created_at: datetime
    updated_at: datetime
