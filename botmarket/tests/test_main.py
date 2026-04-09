import sys
import os
import json
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client(db_setup):
    return TestClient(app)


def test_health_returns_ok(client):
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


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
    assert set(data.keys()) == {"agent_id", "api_key", "cu_balance", "next_step"}


def test_register_ignores_extra_body(client):
    """Sending extra fields in body does not affect registration or response."""
    resp = client.post(
        "/v1/agents/register",
        json={"name": "evil", "email": "bad@bad.com"},
    )
    assert resp.status_code == 201
    assert set(resp.json().keys()) == {"agent_id", "api_key", "cu_balance", "next_step"}


# ── Helper ────────────────────────────────────────────────


def _register(client):
    """Register an agent and return (agent_id, api_key)."""
    data = client.post("/v1/agents/register").json()
    return data["agent_id"], data["api_key"]


def _seed_balance(agent_id, amount):
    """Directly set cu_balance for an agent (test helper)."""
    import db
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?", (amount, agent_id))
    conn.commit()
    conn.close()


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
    """No API key → 401 (missing authentication)."""
    resp = client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
    )
    assert resp.status_code == 401


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
    agent_id, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    _seed_balance(agent_id, 20.0)
    resp = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 100},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201


def test_seller_register_response_fields(client):
    agent_id, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    _seed_balance(agent_id, 20.0)
    data = client.post(
        "/v1/sellers/register",
        json={"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 100},
        headers={"X-API-Key": api_key},
    ).json()
    assert data == {"status": "registered", "capability_hash": cap_hash, "price_cu": 20.0}


def test_seller_persisted_in_db(client):
    agent_id, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    _seed_balance(agent_id, 15.0)
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
    agent_id, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    _seed_balance(agent_id, 20.0)
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
    assert resp.status_code == 401


def test_seller_same_agent_multiple_capabilities(client):
    agent_id, api_key = _register(client)
    h1 = _register_schema(client, api_key)
    h2 = _register_schema(client, api_key, {"type": "image"}, {"type": "label"})
    _seed_balance(agent_id, 30.0)
    client.post("/v1/sellers/register", json={"capability_hash": h1, "price_cu": 10.0, "capacity": 5}, headers={"X-API-Key": api_key})
    client.post("/v1/sellers/register", json={"capability_hash": h2, "price_cu": 20.0, "capacity": 3}, headers={"X-API-Key": api_key})
    r1 = client.get(f"/v1/sellers/{h1}").json()
    r2 = client.get(f"/v1/sellers/{h2}").json()
    assert len(r1["sellers"]) >= 1
    assert len(r2["sellers"]) >= 1


def test_seller_multiple_agents_same_capability(client):
    id1, key1 = _register(client)
    id2, key2 = _register(client)
    cap_hash = _register_schema(client, key1)
    _seed_balance(id1, 30.0)
    _seed_balance(id2, 10.0)
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


# ── GET /v1/sellers/list — verified badge ─────────────────


def test_sellers_list_includes_verified_badge(client):
    """sellers/list returns verified_seller, trade_count, sla_pct fields."""
    _, key, cap_hash = _setup_seller(client, price=1.0)
    data = client.get("/v1/sellers/list").json()
    seller = data["sellers"][0]
    assert "verified_seller" in seller
    assert "trade_count" in seller
    assert "sla_pct" in seller
    assert seller["verified_seller"] is False
    assert seller["trade_count"] == 0


def test_sellers_list_verified_after_10_trades(client):
    """Seller becomes verified after 10 completed trades with 0 violations."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=1.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 1000.0)

    for _ in range(10):
        match = _match_trade(client, buyer_key, cap_hash)
        _execute_trade(client, buyer_key, match["trade_id"])
        client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    data = client.get("/v1/sellers/list").json()
    seller = next(s for s in data["sellers"] if s["agent_pubkey"] == seller_id)
    assert seller["verified_seller"] is True
    assert seller["trade_count"] == 10
    assert seller["sla_pct"] == 100.0


def test_get_sellers_sorted_by_price(client):
    """3 sellers at 30, 10, 20 CU → returned sorted 10, 20, 30."""
    keys = [_register(client) for _ in range(3)]
    cap_hash = _register_schema(client, keys[0][1])
    for (agent_id, key), price in zip(keys, [30.0, 10.0, 20.0]):
        _seed_balance(agent_id, price)
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
    _fund_agent(client, seller_id, price)
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
    for (agent_id, key), price in zip(keys, [30.0, 10.0, 20.0]):
        _seed_balance(agent_id, price)
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
    _seed_balance(keys[0][0], 10.0)
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 10.0, "capacity": 1}, headers={"X-API-Key": keys[0][1]})
    # Seller 2: more expensive but capacity=5
    _seed_balance(keys[1][0], 25.0)
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
    _seed_balance(keys[0][0], 10.0)
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 10.0, "capacity": 5}, headers={"X-API-Key": keys[0][1]})
    _seed_balance(keys[1][0], 30.0)
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
    """No API key → 401."""
    resp = client.post("/v1/match", json={"capability_hash": "abc"})
    assert resp.status_code == 401


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


# ── Helpers for Step 6+ ──────────────────────────────────


def _match_trade(client, buyer_key, cap_hash):
    """Match a trade and return the response data."""
    return client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"X-API-Key": buyer_key}).json()


# ── Step 6: Trade Execution ──────────────────────────────


def test_execute_returns_output(client):
    """Execute valid trade → output returned with latency."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    resp = client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "hello world"},
        headers={"X-API-Key": buyer_key},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "executed"
    assert "output" in data
    assert "latency_us" in data
    assert isinstance(data["latency_us"], int)


def test_execute_response_fields(client):
    """Response has exactly output, latency_us, status."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    data = client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    ).json()
    assert set(data.keys()) == {"output", "latency_us", "status"}


def test_execute_trade_not_found(client):
    """Non-existent trade_id → 404."""
    _, buyer_key = _register(client)
    resp = client.post(
        "/v1/trades/nonexistent/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    )
    assert resp.status_code == 404


def test_execute_wrong_buyer(client):
    """Only the matched buyer can execute → 403 for anyone else."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    # Another agent tries to execute
    _, other_key = _register(client)
    resp = client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": other_key},
    )
    assert resp.status_code == 403


def test_execute_already_executed(client):
    """Trade already executed → 400."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "first"},
        headers={"X-API-Key": buyer_key},
    )
    resp = client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "second"},
        headers={"X-API-Key": buyer_key},
    )
    assert resp.status_code == 400


def test_execute_trade_status_updated(client):
    """Trade status changes from matched to executed."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    )
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT status, latency_us, start_ns, end_ns FROM trades WHERE id = ?", (match["trade_id"],)).fetchone()
    conn.close()
    assert row["status"] == "executed"
    assert row["latency_us"] is not None
    assert row["start_ns"] is not None
    assert row["end_ns"] is not None
    assert row["end_ns"] >= row["start_ns"]


def test_execute_latency_measured(client):
    """Latency = (end_ns - start_ns) / 1000, non-negative integer."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    data = client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    ).json()
    assert data["latency_us"] >= 0


def test_execute_active_calls_decremented(client):
    """Seller active_calls decreases after execution."""
    seller_id, _, cap_hash = _setup_seller(client, price=20.0, capacity=5)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    # After match, active_calls = 1
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT active_calls FROM sellers WHERE agent_pubkey = ?", (seller_id,)).fetchone()
    assert row["active_calls"] == 1
    conn.close()
    # After execute, active_calls = 0
    client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    )
    conn = db.get_connection()
    row = conn.execute("SELECT active_calls FROM sellers WHERE agent_pubkey = ?", (seller_id,)).fetchone()
    conn.close()
    assert row["active_calls"] == 0


def test_execute_event_recorded(client):
    """Event trade_executed recorded with trade_id and latency."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    )
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT event_data FROM events WHERE event_type = 'trade_executed' ORDER BY seq DESC LIMIT 1").fetchone()
    conn.close()
    payload = json.loads(row["event_data"])
    assert payload["trade_id"] == match["trade_id"]
    assert "latency_us" in payload


def test_execute_requires_auth(client):
    """No API key → 401."""
    resp = client.post("/v1/trades/some-id/execute", json={"input": "test"})
    assert resp.status_code == 401


def test_execute_escrow_still_held(client):
    """After execution, escrow remains held (settlement is Step 7)."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    )
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT status, cu_amount FROM escrow WHERE trade_id = ?", (match["trade_id"],)).fetchone()
    conn.close()
    assert row["status"] == "held"
    assert row["cu_amount"] == 20.0


def test_execute_cu_invariant(client):
    """CU invariant holds after execution: sum(bal) + sum(escrow) = total."""
    _, _, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    client.post(
        f"/v1/trades/{match['trade_id']}/execute",
        json={"input": "test"},
        headers={"X-API-Key": buyer_key},
    )
    import db
    conn = db.get_connection()
    total_bal = conn.execute("SELECT SUM(cu_balance) FROM agents").fetchone()[0]
    total_esc = conn.execute("SELECT COALESCE(SUM(cu_amount), 0) FROM escrow").fetchone()[0]
    conn.close()
    assert total_bal + total_esc == 100.0


# ── Helpers for Step 7+ ──────────────────────────────────


def _execute_trade(client, buyer_key, trade_id, input_text="test"):
    """Execute a trade and return response data."""
    return client.post(
        f"/v1/trades/{trade_id}/execute",
        json={"input": input_text},
        headers={"X-API-Key": buyer_key},
    ).json()


def _full_trade_cycle(client, price=20.0, buyer_cu=100.0):
    """Register seller + buyer, match, execute. Returns (buyer_id, buyer_key, seller_id, trade_id, cap_hash)."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=price)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, buyer_cu)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    return buyer_id, buyer_key, seller_id, match["trade_id"], cap_hash


# ── Step 7: Verification + Settlement ────────────────────


def test_settle_pass_returns_completed(client):
    """Settle a valid executed trade → completed."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client, price=20.0)
    resp = client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "seller_receives" in data
    assert "fee_cu" in data


def test_settle_pass_fee_math(client):
    """200 CU trade: seller gets 197.0, fee = 3.0."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client, price=200.0, buyer_cu=500.0)
    data = client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key}).json()
    assert data["seller_receives"] == 197.0
    assert data["fee_cu"] == 3.0


def test_settle_pass_seller_credited(client):
    """Seller cu_balance increases by price × 0.985 after settlement."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client, price=200.0, buyer_cu=500.0)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (seller_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == 197.0


def test_settle_pass_escrow_released(client):
    """Escrow row marked 'released' after successful settlement."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client, price=20.0)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT status FROM escrow WHERE trade_id = ?", (trade_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row["status"] == "released"


def test_settle_pass_trade_status_completed(client):
    """Trade status = completed after settlement."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT status FROM trades WHERE id = ?", (trade_id,)).fetchone()
    conn.close()
    assert row["status"] == "completed"


def test_settle_pass_event_recorded(client):
    """Event settlement_complete recorded with correct fee fields."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client, price=200.0, buyer_cu=500.0)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT event_data FROM events WHERE event_type = 'settlement_complete' ORDER BY seq DESC LIMIT 1").fetchone()
    conn.close()
    payload = json.loads(row["event_data"])
    assert payload["trade_id"] == trade_id
    assert payload["seller_receives"] == 197.0
    assert payload["fee_cu"] == 3.0
    # phantom sub-fees must not appear in event
    assert "fee_platform" not in payload
    assert "fee_makers" not in payload
    assert "fee_verify" not in payload


def test_settle_pass_fee_is_fee_total(client):
    """fee_cu = price * FEE_TOTAL (1.5%)."""
    from constants import FEE_TOTAL
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client, price=200.0, buyer_cu=500.0)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT event_data FROM events WHERE event_type = 'settlement_complete' ORDER BY seq DESC LIMIT 1").fetchone()
    conn.close()
    p = json.loads(row["event_data"])
    assert abs(p["fee_cu"] - 200.0 * FEE_TOTAL) < 1e-9


def test_settle_cu_invariant_after_pass(client):
    """After settlement: sum(balances) + held_escrow + cu_staked + fees = total CU injected."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client, price=200.0, buyer_cu=500.0)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    import db
    conn = db.get_connection()
    total_bal = conn.execute("SELECT SUM(cu_balance) FROM agents").fetchone()[0]
    total_held_esc = conn.execute("SELECT COALESCE(SUM(cu_amount), 0) FROM escrow WHERE status = 'held'").fetchone()[0]
    total_staked = conn.execute("SELECT COALESCE(SUM(cu_staked), 0) FROM sellers").fetchone()[0]
    conn.close()
    # Injected: 500 (buyer) + 200 (seller seed for stake)
    # After staking: seller balance=0, cu_staked=200
    # After trade: buyer=300, seller=197, fees=3
    # total_bal(497) + held_escrow(0) + staked(200) + fees(3) = 700
    total_injected = 700.0
    fees = 200.0 * 0.015  # 3.0
    assert abs((total_bal + total_held_esc + total_staked + fees) - total_injected) < 0.001


def test_settle_trade_not_found(client):
    """Non-existent trade → 404."""
    _, buyer_key = _register(client)
    resp = client.post("/v1/trades/nonexistent/settle", headers={"X-API-Key": buyer_key})
    assert resp.status_code == 404


def test_settle_wrong_buyer(client):
    """Only the buyer can settle → 403 for anyone else."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    _, other_key = _register(client)
    resp = client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": other_key})
    assert resp.status_code == 403


def test_settle_not_executed(client):
    """Trade in matched status (not yet executed) → 400."""
    _, _, cap_hash = _setup_seller(client)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    resp = client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})
    assert resp.status_code == 400


def test_settle_already_completed(client):
    """Already settled trade → 400."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    resp = client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})
    assert resp.status_code == 400


def test_settle_requires_auth(client):
    """No API key → 401."""
    resp = client.post("/v1/trades/some-id/settle")
    assert resp.status_code == 401


def test_settle_fail_latency_exceeded(client):
    """Seller latency_bound_us exceeded → violated, buyer refunded."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    # Manually set latency_bound_us = 1 (1 microsecond — impossible to meet)
    # and trade latency to something high
    import db
    conn = db.get_connection()
    conn.execute("UPDATE sellers SET latency_bound_us = 1 WHERE agent_pubkey = ?", (seller_id,))
    conn.execute("UPDATE trades SET latency_us = 500 WHERE id = ?", (match["trade_id"],))
    conn.commit()
    conn.close()
    data = client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key}).json()
    assert data["status"] == "violated"
    assert data["reason"] == "latency_exceeded"


def test_settle_fail_buyer_refunded(client):
    """On violation, buyer gets escrow CU back."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    # Force latency violation
    import db
    conn = db.get_connection()
    conn.execute("UPDATE sellers SET latency_bound_us = 1 WHERE agent_pubkey = ?", (seller_id,))
    conn.execute("UPDATE trades SET latency_us = 500 WHERE id = ?", (match["trade_id"],))
    conn.commit()
    conn.close()
    client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (buyer_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == 100.5  # 80 (after match debit) + 20 (refund) + 0.5 (slash share) = 100.5


def test_settle_fail_escrow_refunded(client):
    """Escrow marked 'refunded' on violation."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    import db
    conn = db.get_connection()
    conn.execute("UPDATE sellers SET latency_bound_us = 1 WHERE agent_pubkey = ?", (seller_id,))
    conn.execute("UPDATE trades SET latency_us = 500 WHERE id = ?", (match["trade_id"],))
    conn.commit()
    conn.close()
    client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})
    conn = db.get_connection()
    row = conn.execute("SELECT status FROM escrow WHERE trade_id = ?", (match["trade_id"],)).fetchone()
    conn.close()
    assert row is not None
    assert row["status"] == "refunded"


def test_settle_fail_trade_status_violated(client):
    """Trade status = violated after failed verification."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    import db
    conn = db.get_connection()
    conn.execute("UPDATE sellers SET latency_bound_us = 1 WHERE agent_pubkey = ?", (seller_id,))
    conn.execute("UPDATE trades SET latency_us = 500 WHERE id = ?", (match["trade_id"],))
    conn.commit()
    conn.close()
    client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})
    conn = db.get_connection()
    row = conn.execute("SELECT status FROM trades WHERE id = ?", (match["trade_id"],)).fetchone()
    conn.close()
    assert row["status"] == "violated"


def test_settle_fail_event_recorded(client):
    """Event bond_slashed recorded on violation."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    import db
    conn = db.get_connection()
    conn.execute("UPDATE sellers SET latency_bound_us = 1 WHERE agent_pubkey = ?", (seller_id,))
    conn.execute("UPDATE trades SET latency_us = 500 WHERE id = ?", (match["trade_id"],))
    conn.commit()
    conn.close()
    client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})
    conn = db.get_connection()
    row = conn.execute("SELECT event_data FROM events WHERE event_type = 'bond_slashed' ORDER BY seq DESC LIMIT 1").fetchone()
    conn.close()
    payload = json.loads(row["event_data"])
    assert payload["trade_id"] == match["trade_id"]
    assert payload["reason"] == "latency_exceeded"


def test_settle_no_latency_bound_passes(client):
    """latency_bound_us = 0 means no SLA set → always passes latency check."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    data = client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key}).json()
    assert data["status"] == "completed"


# ── Step 8: Event Log ────────────────────────────────


def test_events_full_lifecycle(client):
    """Full trade lifecycle produces agent_registered → schema_registered → seller_registered → match_made → trade_executed → settlement_complete."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    # Query buyer events
    resp = client.get(f"/v1/events/{buyer_id}", headers={"X-API-Key": buyer_key})
    assert resp.status_code == 200
    data = resp.json()
    types = [e["event_type"] for e in data["events"]]
    assert "agent_registered" in types
    assert "match_made" in types
    assert "trade_executed" in types
    assert "settlement_complete" in types


def test_events_seller_lifecycle(client):
    """Seller sees their registration and trade events."""
    buyer_id, buyer_key, seller_id, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    seller_resp = client.get(f"/v1/events/{seller_id}", headers={"X-API-Key": buyer_key})
    seller_types = [e["event_type"] for e in seller_resp.json()["events"]]
    assert "agent_registered" in seller_types
    assert "seller_registered" in seller_types
    assert "match_made" in seller_types
    assert "settlement_complete" in seller_types


def test_events_filter_by_type(client):
    """?event_type= filters to only that type."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    resp = client.get(f"/v1/events/{buyer_id}?event_type=match_made", headers={"X-API-Key": buyer_key})
    data = resp.json()
    assert len(data["events"]) >= 1
    for e in data["events"]:
        assert e["event_type"] == "match_made"


def test_events_limit(client):
    """?limit= caps number of events returned."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    resp = client.get(f"/v1/events/{buyer_id}?limit=2", headers={"X-API-Key": buyer_key})
    data = resp.json()
    assert len(data["events"]) <= 2


def test_events_ordered_by_seq(client):
    """Events returned in seq ASC order."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    resp = client.get(f"/v1/events/{buyer_id}", headers={"X-API-Key": buyer_key})
    events = resp.json()["events"]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)


def test_events_have_timestamp_ns(client):
    """Every event has nanosecond timestamp."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)

    resp = client.get(f"/v1/events/{buyer_id}", headers={"X-API-Key": buyer_key})
    for e in resp.json()["events"]:
        assert e["timestamp_ns"] > 1_000_000_000_000_000_000


def test_events_data_is_raw_json(client):
    """event_data is valid JSON with raw facts, not computed stats."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    resp = client.get(f"/v1/events/{buyer_id}?event_type=settlement_complete", headers={"X-API-Key": buyer_key})
    for e in resp.json()["events"]:
        payload = json.loads(e["event_data"])
        assert "trade_id" in payload
        # No computed stats
        assert "reputation_score" not in payload
        assert "p99" not in payload
        assert "compliance_rate" not in payload


def test_events_agent_not_found(client):
    """Non-existent agent → 404."""
    _, buyer_key = _register(client)
    resp = client.get("/v1/events/nonexistent", headers={"X-API-Key": buyer_key})
    assert resp.status_code == 404


def test_events_requires_auth(client):
    """No API key → 401."""
    resp = client.get("/v1/events/some-id")
    assert resp.status_code == 401


def test_events_only_agent_events(client):
    """Query by agent returns only that agent's events, not others."""
    # Create two separate agents with separate trades
    seller_id1, seller_key1, cap_hash1 = _setup_seller(client, price=10.0)
    buyer_id1, buyer_key1 = _register(client)
    _fund_agent(client, buyer_id1, 100.0)

    buyer_id2, buyer_key2 = _register(client)
    _fund_agent(client, buyer_id2, 100.0)

    # Only buyer1 does a trade
    match1 = _match_trade(client, buyer_key1, cap_hash1)
    _execute_trade(client, buyer_key1, match1["trade_id"])

    # buyer2 events should NOT have match_made from buyer1's trade
    resp2 = client.get(f"/v1/events/{buyer_id2}?event_type=match_made", headers={"X-API-Key": buyer_key2})
    assert len(resp2.json()["events"]) == 0


def test_events_10_trades_all_present(client):
    """Run 10 trades → query events → all 10 match_made events present for buyer."""
    _, _, cap_hash = _setup_seller(client, price=5.0, capacity=20)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 500.0)

    for _ in range(10):
        match = _match_trade(client, buyer_key, cap_hash)
        _execute_trade(client, buyer_key, match["trade_id"])
        client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    resp = client.get(f"/v1/events/{buyer_id}?event_type=match_made", headers={"X-API-Key": buyer_key})
    assert len(resp.json()["events"]) == 10

    resp2 = client.get(f"/v1/events/{buyer_id}?event_type=settlement_complete", headers={"X-API-Key": buyer_key})
    assert len(resp2.json()["events"]) == 10


def test_events_immutable_no_delete(client):
    """Events are immutable — records persist after trades settle."""
    buyer_id, buyer_key, _, trade_id, _ = _full_trade_cycle(client)
    client.post(f"/v1/trades/{trade_id}/settle", headers={"X-API-Key": buyer_key})

    resp_before = client.get(f"/v1/events/{buyer_id}", headers={"X-API-Key": buyer_key})
    count_before = len(resp_before.json()["events"])
    assert count_before > 0

    # No event was lost — query again
    resp_after = client.get(f"/v1/events/{buyer_id}", headers={"X-API-Key": buyer_key})
    assert len(resp_after.json()["events"]) == count_before


def test_events_violation_recorded(client):
    """Bond slash events queryable via event log."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    import db
    conn = db.get_connection()
    conn.execute("UPDATE sellers SET latency_bound_us = 1 WHERE agent_pubkey = ?", (seller_id,))
    conn.execute("UPDATE trades SET latency_us = 500 WHERE id = ?", (match["trade_id"],))
    conn.commit()
    conn.close()
    client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    resp = client.get(f"/v1/events/{seller_id}?event_type=bond_slashed", headers={"X-API-Key": buyer_key})
    events = resp.json()["events"]
    assert len(events) == 1
    payload = json.loads(events[0]["event_data"])
    assert payload["reason"] == "latency_exceeded"


# ── Faucet ────────────────────────────────────────────────


def test_faucet_first_call_credits_500_cu(client):
    """First ever call should credit FAUCET_FIRST_CU (500 CU) to the agent."""
    agent_id, api_key = _register(client)
    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["credited"] == 500.0


def test_faucet_first_call_response_shape(client):
    """First call response must include credited, balance, total_from_faucet, next_drip_at."""
    agent_id, api_key = _register(client)
    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    data = resp.json()
    assert set(data.keys()) == {"credited", "balance", "total_from_faucet", "next_drip_at", "next_step"}
    assert data["balance"] == 500.0
    assert data["total_from_faucet"] == 500.0
    assert data["next_drip_at"] is not None  # more drips possible (500 < 1000 cap)


def test_faucet_credits_agent_balance(client):
    """CU credited by faucet must appear in the agent's balance."""
    agent_id, api_key = _register(client)
    client.post("/v1/faucet", headers={"X-API-Key": api_key})
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (agent_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == 500.0


def test_faucet_second_call_too_soon_returns_zero(client):
    """Second call within the 24h window must credit 0 CU."""
    agent_id, api_key = _register(client)
    client.post("/v1/faucet", headers={"X-API-Key": api_key})
    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["credited"] == 0.0
    assert "too soon" in data["message"]
    assert data["next_drip_at"] is not None


def test_faucet_second_call_after_window_credits_drip(client):
    """After 24h window has elapsed, the drip (50 CU) should be credited."""
    agent_id, api_key = _register(client)
    client.post("/v1/faucet", headers={"X-API-Key": api_key})

    # Backdate last_drip_ns by 25 hours so the window has passed
    import db
    window_ns = 86_400_000_000_000
    conn = db.get_connection()
    conn.execute(
        "UPDATE faucet_state SET last_drip_ns = last_drip_ns - ? WHERE agent_pubkey = ?",
        (window_ns + 1, agent_id),
    )
    conn.commit()
    conn.close()

    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["credited"] == 50.0
    assert data["total_from_faucet"] == 550.0


def test_faucet_lifetime_cap_stops_drip(client):
    """Once total_credited_cu >= FAUCET_MAX_CU (1000), return 0 and cap message."""
    agent_id, api_key = _register(client)
    # Seed faucet_state to the cap directly
    import db
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO faucet_state (agent_pubkey, total_credited_cu, last_drip_ns) VALUES (?, ?, ?)",
        (agent_id, 1000.0, 1),
    )
    conn.commit()
    conn.close()

    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["credited"] == 0.0
    assert "lifetime cap" in data["message"]
    assert data["next_drip_at"] is None


def test_faucet_drip_capped_at_remaining_allowance(client):
    """If only 20 CU remain under the cap, drip must credit 20, not the full 50."""
    agent_id, api_key = _register(client)
    import db
    window_ns = 86_400_000_000_000
    conn = db.get_connection()
    # 980 already credited, window expired
    conn.execute(
        "INSERT INTO faucet_state (agent_pubkey, total_credited_cu, last_drip_ns) VALUES (?, ?, ?)",
        (agent_id, 980.0, 1),
    )
    conn.commit()
    conn.close()

    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["credited"] == 20.0
    assert data["total_from_faucet"] == 1000.0
    assert data["next_drip_at"] is None  # cap reached after this drip


def test_faucet_requires_auth(client):
    """Calling /v1/faucet without auth returns 401."""
    resp = client.post("/v1/faucet")
    assert resp.status_code == 401


def test_faucet_unknown_agent_returns_404(client):
    """If the pubkey is not in the agents table, return 404."""
    # Manually craft an API key for a ghost agent
    import db
    import secrets
    api_key = secrets.token_hex(32)
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, 0.0, 0)",
        ("ghost_pubkey_that_we_will_delete", api_key),
    )
    conn.commit()
    conn.execute("DELETE FROM agents WHERE pubkey = 'ghost_pubkey_that_we_will_delete'")
    conn.commit()
    conn.close()
    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code in (401, 404)  # 401 because key no longer valid, or 404


def test_faucet_disabled_returns_503(client, monkeypatch):
    """When FAUCET_ENABLED is empty, the endpoint returns 503."""
    monkeypatch.setenv("FAUCET_ENABLED", "")
    agent_id, api_key = _register(client)
    resp = client.post("/v1/faucet", headers={"X-API-Key": api_key})
    assert resp.status_code == 503


def test_faucet_records_event(client):
    """A successful drip must create a faucet_drip event."""
    agent_id, api_key = _register(client)
    client.post("/v1/faucet", headers={"X-API-Key": api_key})
    import db
    conn = db.get_connection()
    events = conn.execute(
        "SELECT event_data FROM events WHERE event_type = 'faucet_drip'"
    ).fetchall()
    conn.close()
    assert len(events) == 1
    payload = json.loads(events[0]["event_data"])
    assert payload["agent"] == agent_id
    assert payload["credited"] == 500.0


# ── Leaderboard ──────────────────────────────────────────


def test_leaderboard_empty_when_no_sellers(client):
    """No sellers → empty leaderboard list."""
    resp = client.get("/v1/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["leaderboard"] == []


def test_leaderboard_no_auth_required(client):
    """Leaderboard is a public endpoint — no auth header needed."""
    resp = client.get("/v1/leaderboard")
    assert resp.status_code == 200


def test_leaderboard_response_shape(client):
    """Response must contain leaderboard list and limit."""
    resp = client.get("/v1/leaderboard")
    data = resp.json()
    assert "leaderboard" in data
    assert "limit" in data
    assert data["limit"] == 20


def test_leaderboard_shows_registered_seller(client):
    """A registered seller must appear in the leaderboard."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=5.0)
    resp = client.get("/v1/leaderboard")
    entries = resp.json()["leaderboard"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["agent_pubkey"] == seller_id
    assert entry["capability_hash"] == cap_hash
    assert entry["price_cu"] == 5.0
    assert entry["cu_earned"] == 0.0
    assert entry["trade_count"] == 0
    assert entry["sla_pct"] is None
    assert entry["verified_seller"] is False


def test_leaderboard_entry_fields(client):
    """Each entry must have exactly the expected keys."""
    _setup_seller(client, price=5.0)
    entry = client.get("/v1/leaderboard").json()["leaderboard"][0]
    assert set(entry.keys()) == {
        "agent_pubkey", "capability_hash", "price_cu",
        "cu_earned", "trade_count", "sla_pct", "verified_seller",
        "avg_quality", "quality_votes",
    }


def test_leaderboard_cu_earned_after_completed_trade(client):
    """After a completed trade, cu_earned should equal price * (1 - 0.015)."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=20.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)
    match = _match_trade(client, buyer_key, cap_hash)
    _execute_trade(client, buyer_key, match["trade_id"])
    client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    entries = client.get("/v1/leaderboard").json()["leaderboard"]
    entry = next(e for e in entries if e["agent_pubkey"] == seller_id)
    assert abs(entry["cu_earned"] - 20.0 * 0.985) < 1e-9
    assert entry["trade_count"] == 1
    assert entry["sla_pct"] == 100.0


def test_leaderboard_sorted_by_cu_earned_desc(client):
    """Higher-earning sellers must be ranked first."""
    # Seller A and B need different schemas so the match engine doesn't conflate them
    seller_a, key_a = _register(client)
    hash_a = _register_schema(client, key_a, input_s={"type": "object", "title": "A"})
    _fund_agent(client, seller_a, 5.0)
    client.post("/v1/sellers/register", json={"capability_hash": hash_a, "price_cu": 5.0, "capacity": 10}, headers={"X-API-Key": key_a})

    seller_b, key_b = _register(client)
    hash_b = _register_schema(client, key_b, input_s={"type": "object", "title": "B"})
    _fund_agent(client, seller_b, 20.0)
    client.post("/v1/sellers/register", json={"capability_hash": hash_b, "price_cu": 20.0, "capacity": 10}, headers={"X-API-Key": key_b})

    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 500.0)

    # Each cap_hash has only one seller, so match goes to the intended seller
    for cap_hash, _ in [(hash_a, key_a), (hash_b, key_b)]:
        match = _match_trade(client, buyer_key, cap_hash)
        _execute_trade(client, buyer_key, match["trade_id"])
        client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    entries = client.get("/v1/leaderboard").json()["leaderboard"]
    earnings = [e["cu_earned"] for e in entries]
    assert earnings == sorted(earnings, reverse=True)
    assert entries[0]["agent_pubkey"] == seller_b


def test_leaderboard_verified_seller_badge_requires_10_completed(client):
    """verified_seller is True only for sellers with ≥10 completed trades and 0 violations."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=1.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 1000.0)

    # Complete 10 trades
    for _ in range(10):
        match = _match_trade(client, buyer_key, cap_hash)
        _execute_trade(client, buyer_key, match["trade_id"])
        client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    entries = client.get("/v1/leaderboard").json()["leaderboard"]
    entry = next(e for e in entries if e["agent_pubkey"] == seller_id)
    assert entry["verified_seller"] is True
    assert entry["trade_count"] == 10
    assert entry["sla_pct"] == 100.0


def test_leaderboard_not_verified_below_10_trades(client):
    """verified_seller is False with fewer than 10 completed trades."""
    seller_id, seller_key, cap_hash = _setup_seller(client, price=1.0)
    buyer_id, buyer_key = _register(client)
    _fund_agent(client, buyer_id, 100.0)

    for _ in range(5):
        match = _match_trade(client, buyer_key, cap_hash)
        _execute_trade(client, buyer_key, match["trade_id"])
        client.post(f"/v1/trades/{match['trade_id']}/settle", headers={"X-API-Key": buyer_key})

    entry = client.get("/v1/leaderboard").json()["leaderboard"][0]
    assert entry["verified_seller"] is False


def test_leaderboard_limit_parameter(client):
    """limit query param controls the maximum number of entries returned."""
    for _ in range(5):
        _setup_seller(client, price=1.0)
    resp = client.get("/v1/leaderboard?limit=3")
    data = resp.json()
    assert len(data["leaderboard"]) == 3
    assert data["limit"] == 3


# ── GET /v1/schemas/{hash} ────────────────────────────────


def test_get_schema_returns_correct_fields(client):
    """GET /v1/schemas/{hash} returns input_schema, output_schema, and registered_at."""
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    resp = client.get(f"/v1/schemas/{cap_hash}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["capability_hash"] == cap_hash
    assert "input_schema" in data
    assert "output_schema" in data
    assert "registered_at" in data
    assert isinstance(data["input_schema"], dict)
    assert isinstance(data["output_schema"], dict)


def test_get_schema_no_auth_required(client):
    """GET /v1/schemas/{hash} is a public endpoint."""
    _, api_key = _register(client)
    cap_hash = _register_schema(client, api_key)
    resp = client.get(f"/v1/schemas/{cap_hash}")
    assert resp.status_code == 200


def test_get_schema_unknown_hash_returns_404(client):
    """Unknown capability_hash returns 404."""
    resp = client.get("/v1/schemas/" + "a" * 64)
    assert resp.status_code == 404


# ── GET /v1/agents/me ────────────────────────────────────


def test_get_me_returns_pubkey_and_balance(client):
    """GET /v1/agents/me returns the caller's pubkey and cu_balance."""
    agent_id, api_key = _register(client)
    resp = client.get("/v1/agents/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["pubkey"] == agent_id
    assert data["cu_balance"] == 0.0


def test_get_me_reflects_funded_balance(client):
    """cu_balance returned by /v1/agents/me matches the actual balance."""
    agent_id, api_key = _register(client)
    _fund_agent(client, agent_id, 250.0)
    resp = client.get("/v1/agents/me", headers={"X-API-Key": api_key})
    assert resp.json()["cu_balance"] == 250.0


def test_get_me_requires_auth(client):
    """GET /v1/agents/me without auth returns 401."""
    resp = client.get("/v1/agents/me")
    assert resp.status_code == 401


# ── Self-Registration ────────────────────────────────────


class _FakeResponse:
    status_code = 200


class _FakeAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def head(self, url):
        return _FakeResponse()


@pytest.fixture
def sr_client(client, monkeypatch):
    """Client with httpx.AsyncClient stubbed out so callback_url health checks pass."""
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FakeAsyncClient())
    return client


def _make_capabilities(n=2):
    """Generate n distinct capability specs."""
    return [
        {
            "input_schema": {"type": "text", "task": f"task_{i}"},
            "output_schema": {"type": "text", "result": f"result_{i}"},
            "price_cu": 5.0 + i,
            "capacity": 10 + i,
        }
        for i in range(n)
    ]


def test_self_register_returns_201(sr_client):
    agent_id, api_key = _register(sr_client)
    _seed_balance(agent_id, 100.0)
    resp = sr_client.post(
        "/v1/self-register",
        json={"capabilities": _make_capabilities(2), "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201


def test_self_register_response_shape(sr_client):
    agent_id, api_key = _register(sr_client)
    _seed_balance(agent_id, 100.0)
    data = sr_client.post(
        "/v1/self-register",
        json={"capabilities": _make_capabilities(3), "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    ).json()
    assert data["status"] == "registered"
    assert data["agent_id"] == agent_id
    assert data["callback_url"] == "http://localhost:8001/execute"
    assert len(data["capabilities"]) == 3
    for cap in data["capabilities"]:
        assert "capability_hash" in cap
        assert "price_cu" in cap
        assert "capacity" in cap


def test_self_register_creates_schemas_and_sellers(sr_client):
    agent_id, api_key = _register(sr_client)
    _seed_balance(agent_id, 100.0)
    data = sr_client.post(
        "/v1/self-register",
        json={"capabilities": _make_capabilities(2), "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    ).json()

    import db
    conn = db.get_connection()
    for cap in data["capabilities"]:
        schema_row = conn.execute(
            "SELECT capability_hash FROM schemas WHERE capability_hash = ?",
            (cap["capability_hash"],),
        ).fetchone()
        assert schema_row is not None

        seller_row = conn.execute(
            "SELECT price_cu, callback_url FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
            (agent_id, cap["capability_hash"]),
        ).fetchone()
        assert seller_row is not None
        assert seller_row["callback_url"] == "http://localhost:8001/execute"
    conn.close()


def test_self_register_deducts_bond(sr_client):
    agent_id, api_key = _register(sr_client)
    _seed_balance(agent_id, 50.0)
    caps = _make_capabilities(2)  # price 5.0 and 6.0 → total bond 11.0
    sr_client.post(
        "/v1/self-register",
        json={"capabilities": caps, "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    )
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (agent_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == pytest.approx(50.0 - 5.0 - 6.0)


def test_self_register_auto_faucet(sr_client):
    """Agent with 0 CU and no prior faucet gets auto-faucet on self-register."""
    agent_id, api_key = _register(sr_client)
    caps = [{"input_schema": {"t": "a"}, "output_schema": {"t": "b"}, "price_cu": 5.0, "capacity": 1}]
    resp = sr_client.post(
        "/v1/self-register",
        json={"capabilities": caps, "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    import db
    conn = db.get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (agent_id,)).fetchone()
    faucet = conn.execute("SELECT total_credited_cu FROM faucet_state WHERE agent_pubkey = ?", (agent_id,)).fetchone()
    conn.close()
    assert row["cu_balance"] == pytest.approx(500.0 - 5.0)
    assert faucet["total_credited_cu"] == 500.0


def test_self_register_insufficient_cu(sr_client):
    """Reject if agent doesn't have enough CU even after auto-faucet."""
    agent_id, api_key = _register(sr_client)
    caps = [
        {"input_schema": {"t": f"x{i}"}, "output_schema": {"t": f"y{i}"}, "price_cu": 200.0, "capacity": 1}
        for i in range(3)
    ]
    resp = sr_client.post(
        "/v1/self-register",
        json={"capabilities": caps, "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400
    assert "insufficient CU" in resp.json()["detail"]


def test_self_register_empty_capabilities_rejected(sr_client):
    _, api_key = _register(sr_client)
    resp = sr_client.post(
        "/v1/self-register",
        json={"capabilities": [], "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 400


def test_self_register_requires_auth(sr_client):
    resp = sr_client.post(
        "/v1/self-register",
        json={"capabilities": _make_capabilities(1), "callback_url": "http://localhost:8001/execute"},
    )
    assert resp.status_code == 401


def test_self_register_idempotent_schema(sr_client):
    """Re-registering the same capabilities updates sellers, doesn't duplicate schemas."""
    agent_id, api_key = _register(sr_client)
    _seed_balance(agent_id, 100.0)
    caps = _make_capabilities(1)

    data1 = sr_client.post(
        "/v1/self-register",
        json={"capabilities": caps, "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    ).json()

    data2 = sr_client.post(
        "/v1/self-register",
        json={"capabilities": caps, "callback_url": "http://localhost:8001/execute"},
        headers={"X-API-Key": api_key},
    ).json()

    assert data1["capabilities"][0]["capability_hash"] == data2["capabilities"][0]["capability_hash"]

    import db
    conn = db.get_connection()
    schema_count = conn.execute("SELECT COUNT(*) as cnt FROM schemas").fetchone()["cnt"]
    seller_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM sellers WHERE agent_pubkey = ?", (agent_id,)
    ).fetchone()["cnt"]
    conn.close()
    assert schema_count == 1
    assert seller_count == 1
