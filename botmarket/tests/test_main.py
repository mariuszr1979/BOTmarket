import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BOTMARKET_DB", str(tmp_path / "test.db"))
    import db
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()
    return TestClient(app)


def test_health_returns_ok(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
