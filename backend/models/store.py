from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import UUID, uuid4

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class UserRecord:
    id: str
    email: str
    hashed_password: str
    created_at: str


@dataclass
class DocumentRecord:
    id: str
    filename: str
    path: str
    page_count: int
    chunk_count: int
    uploaded_at: str
    owner_id: str


@dataclass
class ChunkRecord:
    id: str
    document_id: str
    filename: str
    page: int
    text: str
    embedding: list[float]


@dataclass
class SessionRecord:
    id: str
    owner_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MemoryStore:
    """Simple JSON-backed store for demos (users, docs, chunks, sessions)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = Lock()
        self.users: dict[str, UserRecord] = {}
        self.documents: dict[str, DocumentRecord] = {}
        self.chunks: list[ChunkRecord] = []
        self.sessions: dict[str, SessionRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.users = {k: UserRecord(**v) for k, v in data.get("users", {}).items()}
        self.documents = {k: DocumentRecord(**v) for k, v in data.get("documents", {}).items()}
        self.chunks = [ChunkRecord(**c) for c in data.get("chunks", [])]
        self.sessions = {k: SessionRecord(**v) for k, v in data.get("sessions", {}).items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": {k: asdict(v) for k, v in self.users.items()},
            "documents": {k: asdict(v) for k, v in self.documents.items()},
            "chunks": [asdict(c) for c in self.chunks],
            "sessions": {k: asdict(v) for k, v in self.sessions.items()},
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        needle = email.lower()
        return next((u for u in self.users.values() if u.email == needle), None)

    def create_user(self, email: str, password: str) -> UserRecord:
        with self.lock:
            if any(u.email.lower() == email.lower() for u in self.users.values()):
                raise ValueError("Email already registered")
            user = UserRecord(
                id=str(uuid4()),
                email=email.lower(),
                hashed_password=pwd_context.hash(password),
                created_at=datetime.utcnow().isoformat(),
            )
            self.users[user.id] = user
            self.save()
            return user

    def ensure_user(self, email: str, password: str) -> UserRecord:
        """Create user if missing; leave existing password unchanged."""
        existing = self.get_user_by_email(email)
        if existing:
            return existing
        return self.create_user(email, password)

    def authenticate(self, email: str, password: str) -> Optional[UserRecord]:
        user = next((u for u in self.users.values() if u.email == email.lower()), None)
        if not user or not pwd_context.verify(password, user.hashed_password):
            return None
        return user

    def get_user(self, user_id: UUID | str) -> Optional[UserRecord]:
        return self.users.get(str(user_id))

    def add_document(self, doc: DocumentRecord, chunks: list[ChunkRecord]) -> DocumentRecord:
        with self.lock:
            self.documents[doc.id] = doc
            self.chunks = [c for c in self.chunks if c.document_id != doc.id] + chunks
            self.save()
            return doc

    def list_documents(self, owner_id: UUID | str) -> list[DocumentRecord]:
        oid = str(owner_id)
        return [d for d in self.documents.values() if d.owner_id == oid]

    def get_document(self, doc_id: UUID | str, owner_id: UUID | str) -> Optional[DocumentRecord]:
        doc = self.documents.get(str(doc_id))
        if not doc or doc.owner_id != str(owner_id):
            return None
        return doc

    def delete_document(self, doc_id: UUID | str, owner_id: UUID | str) -> bool:
        with self.lock:
            doc = self.get_document(doc_id, owner_id)
            if not doc:
                return False
            self.documents.pop(doc.id, None)
            self.chunks = [c for c in self.chunks if c.document_id != doc.id]
            path = Path(doc.path)
            if path.exists():
                path.unlink()
            self.save()
            return True

    def get_or_create_session(self, owner_id: UUID | str, session_id: Optional[UUID] = None) -> SessionRecord:
        with self.lock:
            if session_id and str(session_id) in self.sessions:
                session = self.sessions[str(session_id)]
                if session.owner_id != str(owner_id):
                    raise PermissionError("Session not found")
                return session
            session = SessionRecord(id=str(uuid4()), owner_id=str(owner_id))
            self.sessions[session.id] = session
            self.save()
            return session

    def append_messages(self, session_id: str, messages: list[dict[str, Any]]) -> SessionRecord:
        with self.lock:
            session = self.sessions[session_id]
            session.messages.extend(messages)
            self.save()
            return session
