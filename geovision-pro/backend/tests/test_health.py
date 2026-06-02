"""Smoke test for the health endpoint (no model download required)."""
import os

os.environ.setdefault("GEOVISION_DATABASE_URL", "sqlite+aiosqlite:///./test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
