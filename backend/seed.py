from __future__ import annotations

from backend.models.store import SQLiteStore, UserRecord

# Pre-filled on the login screen — use these to sign in without registering.
DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"


def seed_demo_user(store: SQLiteStore) -> UserRecord:
    return store.ensure_user(DEMO_EMAIL, DEMO_PASSWORD)
