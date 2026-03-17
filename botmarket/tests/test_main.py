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
    import matching
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db()
    matching._seller_tables.clear()
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


# ── Helpers for Step 4+ ──────────────────────────────────


def _register_schema(client, api_key, input_s=None, output_s=None):
    """Register a schema and return the capability_hash."""
    inp = input_s or SAMPLE_INPUT
    out = output_s or SAMPLE_OUTPUT
    return client.post(
        "/v1/schemas/register",
        json={"input_schema": inp, "output_schema": out},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]


# ── Step 4: Seller Registration ──────────────────────────


def test_seller_register_returns_201(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 100},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201


def test_seller_register_response_fields(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    data = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 100},
        headers={"X-API-Key": api_key},
    ).json()
    assert data == {"status": "registered", "capability_hash": cap_hash, "price_cu": 20.0}


def test_seller_persisted_in_db(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 15.0, "capacity": 50},
        headers={"X-API-Key": api_key},
    )
    import db
    conn = db.get_connection()
    row = conn.execute(
        "SELECT price_cu, capacity FROM sellers WHERE capability_hash = ?",
        (cap_hash,),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["price_cu"] == 15.0
    assert row["capacity"] == 50


def test_seller_records_event(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 10},
        headers={"X-API-Key": api_key},
    )
    import db
    conn = db.get_connection()
    row = conn.execute(
        "SELECT event_data FROM events WHERE event_type = 'seller_registered' ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    conn.close()
    payload = json.loads(row["event_data"])
    assert payload["capability_hash"] == cap_hash
    assert payload["price_cu"] == 20.0


def test_seller_reject_bad_capability_hash(client):
    _, api_key = _register(client)
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": "nonexistent", "price_cu": 10.0, "capacity": 5},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 404


def test_seller_reject_zero_price(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 0, "capacity": 10},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400


def test_seller_reject_negative_price(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": -5.0, "capacity": 10},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400


def test_seller_reject_zero_capacity(client):
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 10.0, "capacity": 0},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400


def test_seller_requires_auth(client):
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": "abc", "price_cu": 10.0, "capacity": 5},
    )
    assert resp.status_code == 422


def test_seller_same_agent_multiple_capabilities(client):
    _, api_key = _register(client)
    h1 = _register_schema(client, api_key)
    h2 = _register_schema(client, api_key, {"type": "image"}, {"type": "label"})
    client.post("/v1/sellers/register", json={"capability_hash": h1, "price_cu": 10.0, "capacity": 5}, headers={"X-API-Key": api_key})
    client.post("/v1/sellers/register", json={"capability_hash": h2, "price_cu": 20.0, "capacity": 3}, headers={"X-API-Key": api_key})
    r1 = client.get(f"/v1/sellers/{h1}").json()
    r2 = client.get(f"/v1/sellers/{h2}").json()
    assert len(r1["sellers"]) >= 1
    assert len(r2["sellers"]) >= 1


def test_seller_multiple_agents_same_capability(client):
    _, key1 = _register(client)
    _, key2 = _register(client)
    cap_hash = _register_schema(client, key1)
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 30.0, "capacity": 5}, headers={"X-API-Key": key1})
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 10.0, "capacity": 5}, headers={"X-API-Key": key2})
    data = client.get(f"/v1/sellers/{cap_hash}").json()
    assert len(data["sellers"]) == 2
    # Sorted by price ASC
    assert data["sellers"][0]["price_cu"] == 10.0
    assert data["sellers"][1]["price_cu"] == 30.0


def test_get_sellers_empty(client):
    data = client.get("/v1/sellers/nonexistent_hash").json()
    assert data["sellers"] == []


def test_get_sellers_sorted_by_price(client):
    """3 sellers at 30, 10, 20 CU → returned sorted 10, 20, 30."""
    keys = [_register(client) for _ in range(3)]
    cap_hash = _register_schema(client, keys[0][1])
    for (_, key), price in zip(keys, [30.0, 10.0, 20.0]):
        client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": price, "capacity": 5}, headers={"X-API-Key": key})
    data = client.get(f"/v1/sellers/{cap_hash}").json()
    prices = [s["price_cu"] for s in data["sellers"]]
    assert prices == [10.0, 20.0, 30.0]


# ── Helpers for Step 5+ ──────────────────────────────────


def _fund_agent(client, agent_id, amount):
    """Directly set cu_balance for an agent (test helper)."""
    import db
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?", (amount, agent_id))
    conn.commit()
    conn.close()


def _setup_seller(client, price=20.0, capacity=10):
    """Register agent + schema + seller. Returns (seller_id, seller_key, cap_hash)."""
    seller_id, seller_key = _register(client)
    cap_hash = _register_schema(client, seller_key)
    client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": price, "capacity": capacity},
        headers={"X-API-Key": seller_key},
    )
    return seller_id, seller_key, cap_hash


# ── Step 5: Match Engine ─────────────────────────────────


def test_match_returns_matched(client):
    """Buyer with enough CU gets matched to a seller."""
    seller_id, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    resp = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "matched"
    assert data["seller_pubkey"] == seller_id
    assert data["price_cu"] == 20.0
    assert "trade_id" in data


def test_match_response_fields(client):
    """Response has exactly trade_id, seller_pubkey, price_cu, status."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    assert set(data.keys()) == {"trade_id", "seller_pubkey", "price_cu", "status"}


def test_match_no_sellers(client):
    """No sellers for hash → no_match."""
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": "nonexistent"}, headers={"X-API-Key": buyer_key}).json()
    assert data == {"status": "no_match"}


def test_match_insufficient_cu(client):
    """Buyer has 0 CU → insufficient_cu."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    _, buyer_key = _register(client)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    assert data == {"status": "insufficient_cu"}


def test_match_buyer_cu_debited(client):
    """Buyer CU decreases by price after match."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (buyer_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == 80.0


def test_match_escrow_created(client):
    """Escrow row created with held status and correct amount."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_amount, status FROM escrow WHERE trade_id = ?", (data["trade_id"],)).fetchone()
    conn.close()
    assert row["cu_amount"] == 20.0
    assert row["status"] == "held"


def test_match_trade_created(client):
    """Trade row created with status=matched."""
    seller_id, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT buyer_pubkey, seller_pubkey, price_cu, status FROM trades WHERE id = ?", (data["trade_id"],)).fetchone()
    conn.close()
    assert row["buyer_pubkey"] == buyer_id
    assert row["seller_pubkey"] == seller_id
    assert row["price_cu"] == 20.0
    assert row["status"] == "matched"


def test_match_event_recorded(client):
    """Event match_made recorded with trade details."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT event_data FROM events WHERE event_type = 'match_made' ORDER BY seq DESC LIMIT 1").fetchone()
    conn.close()
    payload = json.loads(row["event_data"])
    assert payload["trade_id"] == data["trade_id"]
    assert payload["buyer"] == buyer_id
    assert payload["price_cu"] == 20.0


def test_match_active_calls_incremented(client):
    """Seller active_calls increases by 1 after match."""
    seller_id, _, cap_hash = _setup_seller(client, price=20.0, capacity=5)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT active_calls FROM sellers WHERE agent_pubkey = ?", (seller_id,)).fetchone()
    conn.close()
    assert row["active_calls"] == 1


def test_match_cheapest_seller_wins(client):
    """3 sellers at 30, 10, 20 → buyer gets the 10 CU seller."""
    keys = [_register(client) for _ in range(3)]
    cap_hash = _register_schema(client, keys[0][1])
    for (_, key), price in zip(keys, [30.0, 10.0, 20.0]):
        client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": price, "capacity": 5}, headers={"X-API-Key": key})
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    assert data["price_cu"] == 10.0
    assert data["seller_pubkey"] == keys[1][0]


def test_match_cheapest_at_capacity_skipped(client):
    """Cheapest seller at capacity → buyer gets next cheapest."""
    keys = [_register(client) for _ in range(2)]
    cap_hash = _register_schema(client, keys[0][1])
    # Seller 1: cheap but capacity=1
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 10.0, "capacity": 1}, headers={"X-API-Key": keys[0][1]})
    # Seller 2: more expensive but capacity=5
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 25.0, "capacity": 5}, headers={"X-API-Key": keys[1][1]})
    # First buyer takes the cheap seller
    buyer1_id, buyer1_key = _register(client)
    _fund_agent(client, buyer1_id, 100.0)
    d1 = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer1_key}).json()
    assert d1["price_cu"] == 10.0
    # Second buyer → cheap seller at capacity → gets the 25 CU seller
    buyer2_id, buyer2_key = _register(client)
    _fund_agent(client, buyer2_id, 100.0)
    d2 = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer2_key}).json()
    assert d2["price_cu"] == 25.0


def test_match_max_price_filter(client):
    """max_price_cu filters out sellers above the limit."""
    keys = [_register(client) for _ in range(2)]
    cap_hash = _register_schema(client, keys[0][1])
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 10.0, "capacity": 5}, headers={"X-API-Key": keys[0][1]})
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 30.0, "capacity": 5}, headers={"X-API-Key": keys[1][1]})
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    # max_price_cu=5 → even the 10 CU seller is too expensive
    data = client.post("/v1/match", json={"capability_hash": cap_hash, "max_price_cu": 5.0}, headers={"X-API-Key": buyer_key}).json()
    assert data["status"] == "no_match"


def test_match_max_price_allows_equal(client):
    """max_price_cu=10 allows a 10 CU seller (<=, not <)."""
    _, _, cap_hash = _setup_seller(client, price=10.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash, "max_price_cu": 10.0}, headers={"X-API-Key": buyer_key}).json()
    assert data["status"] == "matched"
    assert data["price_cu"] == 10.0


def test_match_buyer_balance_never_negative(client):
    """Buyer with 15 CU, seller at 20 CU → insufficient, no negative balance."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 15.0)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    assert data["status"] == "insufficient_cu"
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (buyer_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == 15.0  # unchanged


def test_match_cu_invariant(client):
    """sum(balances) + sum(escrow) = total CU in system."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    total_balances = conn.execute("SELECT SUM(cu_balance) FROM agents").fetchone()[0]
    total_escrow = conn.execute("SELECT COALESCE(SUM(cu_amount), 0) FROM escrow").fetchone()[0]
    conn.close()
    assert total_balances + total_escrow == 100.0


def test_match_requires_auth(client):
    """No API key → 422."""
    resp = client.post("/v1/match", json={"capability_hash": "abc"})
    assert resp.status_code == 422


def test_match_no_partial_fills(client):
    """Full price or no match — no partial fills."""
    _, _, cap_hash = _setup_seller(client, price=50.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 49.99)
    data = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    assert data["status"] == "insufficient_cu"


def test_match_no_resting_orders(client):
    """Match is instant one-shot — two matches use two separate trades."""
    _, _, cap_hash = _setup_seller(client, price=10.0, capacity=5)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    d1 = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    d2 = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()
    assert d1["trade_id"] != d2["trade_id"]
    assert d1["status"] == "matched"
    assert d2["status"] == "matched"
