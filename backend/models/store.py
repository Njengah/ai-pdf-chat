from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import UUID, uuid4

from passlib.context import CryptContext

from backend.db import connect, init_db

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


class SQLiteStore:
    """SQLite-backed store for users, documents, chunks, and chat sessions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = Lock()
        self.conn = connect(path)
        init_db(self.conn)

    def close(self) -> None:
        self.conn.close()

    def get_user_by_email(self, email: str) -> Optional[UserRecord]:
        row = self.conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),),
        ).fetchone()
        return self._user_from_row(row) if row else None

    def create_user(self, email: str, password: str) -> UserRecord:
        with self.lock:
            if self.get_user_by_email(email):
                raise ValueError("Email already registered")
            user = UserRecord(
                id=str(uuid4()),
                email=email.lower(),
                hashed_password=pwd_context.hash(password),
                created_at=datetime.utcnow().isoformat(),
            )
            self.conn.execute(
                "INSERT INTO users (id, email, hashed_password, created_at) VALUES (?, ?, ?, ?)",
                (user.id, user.email, user.hashed_password, user.created_at),
            )
            self.conn.commit()
            return user

    def ensure_user(self, email: str, password: str) -> UserRecord:
        existing = self.get_user_by_email(email)
        if existing:
            return existing
        return self.create_user(email, password)

    def authenticate(self, email: str, password: str) -> Optional[UserRecord]:
        user = self.get_user_by_email(email)
        if not user or not pwd_context.verify(password, user.hashed_password):
            return None
        return user

    def get_user(self, user_id: UUID | str) -> Optional[UserRecord]:
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (str(user_id),),
        ).fetchone()
        return self._user_from_row(row) if row else None

    def add_document(self, doc: DocumentRecord, chunks: list[ChunkRecord]) -> DocumentRecord:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO documents
                (id, filename, path, page_count, chunk_count, uploaded_at, owner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id,
                    doc.filename,
                    doc.path,
                    doc.page_count,
                    doc.chunk_count,
                    doc.uploaded_at,
                    doc.owner_id,
                ),
            )
            self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc.id,))
            for chunk in chunks:
                self.conn.execute(
                    """
                    INSERT INTO chunks
                    (id, document_id, filename, page, text, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.id,
                        chunk.document_id,
                        chunk.filename,
                        chunk.page,
                        chunk.text,
                        json.dumps(chunk.embedding),
                    ),
                )
            self.conn.commit()
            return doc

    def list_documents(self, owner_id: UUID | str) -> list[DocumentRecord]:
        rows = self.conn.execute(
            "SELECT * FROM documents WHERE owner_id = ? ORDER BY uploaded_at DESC",
            (str(owner_id),),
        ).fetchall()
        return [self._doc_from_row(r) for r in rows]

    def get_document(self, doc_id: UUID | str, owner_id: UUID | str) -> Optional[DocumentRecord]:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE id = ? AND owner_id = ?",
            (str(doc_id), str(owner_id)),
        ).fetchone()
        return self._doc_from_row(row) if row else None

    def delete_document(self, doc_id: UUID | str, owner_id: UUID | str) -> bool:
        with self.lock:
            doc = self.get_document(doc_id, owner_id)
            if not doc:
                return False
            self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc.id,))
            self.conn.execute("DELETE FROM documents WHERE id = ?", (doc.id,))
            self.conn.commit()
            path = Path(doc.path)
            if path.exists():
                path.unlink()
            return True

    def list_chunks(self, document_ids: Optional[set[str]] = None) -> list[ChunkRecord]:
        if document_ids is not None:
            if not document_ids:
                return []
            placeholders = ",".join("?" for _ in document_ids)
            rows = self.conn.execute(
                f"SELECT * FROM chunks WHERE document_id IN ({placeholders})",
                tuple(document_ids),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM chunks").fetchall()
        return [self._chunk_from_row(r) for r in rows]

    def get_or_create_session(
        self, owner_id: UUID | str, session_id: Optional[UUID] = None
    ) -> SessionRecord:
        with self.lock:
            if session_id:
                session = self.get_session(session_id)
                if session:
                    if session.owner_id != str(owner_id):
                        raise PermissionError("Session not found")
                    return session
            session = SessionRecord(id=str(uuid4()), owner_id=str(owner_id))
            self.conn.execute(
                "INSERT INTO sessions (id, owner_id, created_at) VALUES (?, ?, ?)",
                (session.id, session.owner_id, session.created_at),
            )
            self.conn.commit()
            return session

    def get_session(self, session_id: UUID | str) -> Optional[SessionRecord]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (str(session_id),),
        ).fetchone()
        if not row:
            return None
        messages = self._load_messages(str(session_id))
        return SessionRecord(
            id=row["id"],
            owner_id=row["owner_id"],
            created_at=row["created_at"],
            messages=messages,
        )

    def append_messages(self, session_id: str, messages: list[dict[str, Any]]) -> SessionRecord:
        with self.lock:
            start = self.conn.execute(
                "SELECT COALESCE(MAX(position), -1) AS m FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()["m"]
            for offset, message in enumerate(messages, start=1):
                created = message.get("created_at") or datetime.utcnow().isoformat()
                if not isinstance(created, str):
                    created = str(created)
                self.conn.execute(
                    """
                    INSERT INTO messages
                    (session_id, role, content, sources, created_at, position)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        message["role"],
                        message["content"],
                        json.dumps(message.get("sources") or []),
                        created,
                        start + offset,
                    ),
                )
            self.conn.commit()
            session = self.get_session(session_id)
            assert session is not None
            return session

    def _load_messages(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT role, content, sources, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY position ASC
            """,
            (session_id,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "sources": json.loads(row["sources"] or "[]"),
                    "created_at": row["created_at"],
                }
            )
        return out

    @staticmethod
    def _user_from_row(row: Any) -> UserRecord:
        return UserRecord(
            id=row["id"],
            email=row["email"],
            hashed_password=row["hashed_password"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _doc_from_row(row: Any) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            filename=row["filename"],
            path=row["path"],
            page_count=row["page_count"],
            chunk_count=row["chunk_count"],
            uploaded_at=row["uploaded_at"],
            owner_id=row["owner_id"],
        )

    @staticmethod
    def _chunk_from_row(row: Any) -> ChunkRecord:
        return ChunkRecord(
            id=row["id"],
            document_id=row["document_id"],
            filename=row["filename"],
            page=row["page"],
            text=row["text"],
            embedding=json.loads(row["embedding"]),
        )


# Back-compat alias used by older imports during transition.
MemoryStore = SQLiteStore
