from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api import deps
from backend.config import get_settings
from backend.main import app
from backend.models.store import SQLiteStore
from backend.seed import seed_demo_user


@pytest.fixture()
def client(monkeypatch):
    base = ROOT / ".pytest_tmp" / "run"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)

    upload_dir = base / "uploads"
    db_path = base / "app.db"
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("APP_SECRET", "test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    store = SQLiteStore(db_path)
    seed_demo_user(store)
    deps._store = store

    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()
    if deps._store is not None:
        deps._store.close()
    deps._store = None
    shutil.rmtree(base, ignore_errors=True)
