import sys
import os
import json
import uuid

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


# ── Step 2: Agent Registration ────────────────────────────


def test_register_returns_201(client):
    resp = client.post("/v1/agents/register")
    assert resp.status_code == 201


def test_register_returns_agent_id_and_api_key(client):
    data = client.post("/v1/agents/register").json()
    assert "agent_id" in data
    assert "api_key" in data
    assert "cu_balance" in data


def test_register_agent_id_is_uuid(client):
    data = client.post("/v1/agents/register").json()
    parsed = uuid.UUID(data["agent_id"])
    assert str(parsed) == data["agent_id"]


def test_register_api_key_is_64_hex(client):
    data = client.post("/v1/agents/register").json()
    assert len(data["api_key"]) == 64
    int(data["api_key"], 16)  # raises ValueError if not hex


def test_register_cu_balance_is_zero(client):
    """Rule 6: earn-first — cu_balance = 0.0 at registration, no grants."""
    data = client.post("/v1/agents/register").json()
    assert data["cu_balance"] == 0.0


def test_register_persisted_in_db(client):
    data = client.post("/v1/agents/register").json()
    import db
    conn = db.get_connection()
    row = conn.execute(
        "SELECT pubkey, api_key, cu_balance FROM agents WHERE pubkey = ?",
        (data["agent_id"],),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["pubkey"] == data["agent_id"]
    assert row["api_key"] == data["api_key"]
    assert row["cu_balance"] == 0.0


def test_register_records_event(client):
    data = client.post("/v1/agents/register").json()
    import db
    conn = db.get_connection()
    row = conn.execute(
        "SELECT event_type, event_data FROM events WHERE event_type = 'agent_registered' ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["event_type"] == "agent_registered"
    payload = json.loads(row["event_data"])
    assert payload["agent"] == data["agent_id"]


def test_register_100_unique_agents(client):
    """Registering 100 agents → all get unique pubkeys and api_keys."""
    results = [client.post("/v1/agents/register").json() for _ in range(100)]
    pubkeys = {r["agent_id"] for r in results}
    api_keys = {r["api_key"] for r in results}
    assert len(pubkeys) == 100
    assert len(api_keys) == 100


def test_register_no_extra_fields(client):
    """Rule 2: no name, email, or profile fields in response."""
    data = client.post("/v1/agents/register").json()
    assert set(data.keys()) == {"agent_id", "api_key", "cu_balance"}


def test_register_ignores_extra_body(client):
    """Sending extra fields in body does not affect registration or response."""
    resp = client.post(
        "/v1/agents/register",
        json={"name": "evil", "email": "bad@bad.com"},
    )
    assert resp.status_code == 201
    assert set(resp.json().keys()) == {"agent_id", "api_key", "cu_balance"}


# ── Helper ────────────────────────────────────────────────


def _register(client):
    """Register an agent and return (agent_id, api_key)."""
    data = client.post("/v1/agents/register").json()
    return data["agent_id"], data["api_key"]


SAMPLE_INPUT = {"type": "text", "max_bytes": 100000}
SAMPLE_OUTPUT = {"type": "text", "max_bytes": 5000}


# ── Step 3: Schema Store ─────────────────────────────────


def test_schema_register_returns_201(client):
    _, api_key = _register(client)
    resp = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201


def test_schema_register_returns_capability_hash(client):
    _, api_key = _register(client)
    data = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()
    assert "capability_hash" in data
    assert len(data["capability_hash"]) == 64  # SHA-256 hex


def test_schema_hash_is_deterministic(client):
    """Same input+output schema always produces same hash."""
    _, api_key = _register(client)
    h1 = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]
    h2 = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]
    assert h1 == h2


def test_schema_different_schemas_different_hash(client):
    _, api_key = _register(client)
    h1 = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]
    h2 = client.post(
        "/v1/schemas/register",
        json={"input_schema": {"type": "image"}, "output_schema": {"type": "label"}},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]
    assert h1 != h2


def test_schema_key_order_irrelevant(client):
    """Canonical JSON (sorted keys) → key order in request doesn't matter."""
    _, api_key = _register(client)
    h1 = client.post(
        "/v1/schemas/register",
        json={"input_schema": {"b": 2, "a": 1}, "output_schema": {"z": 9}},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]
    h2 = client.post(
        "/v1/schemas/register",
        json={"input_schema": {"a": 1, "b": 2}, "output_schema": {"z": 9}},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]
    assert h1 == h2


def test_schema_duplicate_only_one_row(client):
    """INSERT OR IGNORE → 10 registrations of same schema = 1 row in DB."""
    _, api_key = _register(client)
    body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
    for _ in range(10):
        client.post("/v1/schemas/register", json=body, headers={"X-API-Key": api_key})
    import db
    conn = db.get_connection()
    count = conn.execute("SELECT COUNT(*) FROM schemas").fetchone()[0]
    conn.close()
    assert count == 1


def test_schema_persisted_in_db(client):
    _, api_key = _register(client)
    data = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()
    import db
    conn = db.get_connection()
    row = conn.execute(
        "SELECT capability_hash, input_schema, output_schema FROM schemas WHERE capability_hash = ?",
        (data["capability_hash"],),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["capability_hash"] == data["capability_hash"]


def test_schema_records_event(client):
    _, api_key = _register(client)
    data = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()
    import db
    conn = db.get_connection()
    row = conn.execute(
        "SELECT event_type, event_data FROM events WHERE event_type = 'schema_registered' ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    payload = json.loads(row["event_data"])
    assert payload["capability_hash"] == data["capability_hash"]


def test_schema_requires_auth(client):
    """No API key → 422 (missing header)."""
    resp = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
    )
    assert resp.status_code == 422


def test_schema_invalid_api_key(client):
    """Bad API key → 401."""
    resp = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": "0" * 64},
    )
    assert resp.status_code == 401


def test_schema_no_extra_fields_in_response(client):
    """Response contains only capability_hash — no labels, categories, descriptions."""
    _, api_key = _register(client)
    data = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()
    assert set(data.keys()) == {"capability_hash"}
