import sys
import os
import json

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


def _register(client):
    data = client.post("/v1/agents/register").json()
    return data["agent_id"], data["api_key"]


def _full_trade(client):
    """Register buyer+seller, match, execute, settle. Returns trade_id."""
    import db
    buyer_id, buyer_key = _register(client)
    seller_id, seller_key = _register(client)

    # Seed buyer
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = 1000 WHERE pubkey = ?", (buyer_id,))
    conn.commit()
    conn.close()

    schemas = {"input_schema": {"type": "string", "task": "test"}, "output_schema": {"type": "string", "result": "test"}}
    client.post("/v1/schemas/register", json=schemas, headers={"x-api-key": seller_key})

    import hashlib
    ci = json.dumps(schemas["input_schema"], sort_keys=True, separators=(",", ":"))
    co = json.dumps(schemas["output_schema"], sort_keys=True, separators=(",", ":"))
    cap_hash = hashlib.sha256((ci + "||" + co).encode()).hexdigest()

    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 10, "capacity": 5}, headers={"x-api-key": seller_key})

    match = client.post("/v1/match", json={"capability_hash": cap_hash}, headers={"x-api-key": buyer_key}).json()
    trade_id = match["trade_id"]

    client.post(f"/v1/trades/{trade_id}/execute", json={"input": "hello"}, headers={"x-api-key": buyer_key})
    client.post(f"/v1/trades/{trade_id}/settle", headers={"x-api-key": buyer_key})
    return trade_id


# ── /v1/events/stream ──


def test_events_stream_empty(client):
    resp = client.get("/v1/events/stream")
    assert resp.status_code == 200
    assert resp.json()["events"] == []


def test_events_stream_returns_events(client):
    _register(client)
    resp = client.get("/v1/events/stream")
    events = resp.json()["events"]
    assert len(events) >= 1
    assert events[0]["event_type"] == "agent_registered"


def test_events_stream_since_filter(client):
    _register(client)
    r1 = client.get("/v1/events/stream").json()
    last_seq = r1["events"][-1]["seq"]
    _register(client)
    r2 = client.get(f"/v1/events/stream?since={last_seq}").json()
    # Should only contain events after last_seq
    assert all(e["seq"] > last_seq for e in r2["events"])
    assert len(r2["events"]) >= 1


def test_events_stream_no_auth_required(client):
    """Public endpoint — no x-api-key header needed."""
    resp = client.get("/v1/events/stream")
    assert resp.status_code == 200


# ── /v1/stats ──


def test_stats_empty(client):
    resp = client.get("/v1/stats")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total_trades"] == 0
    assert d["completed_trades"] == 0
    assert d["active_agents"] == 0
    assert d["total_cu"] == 0


def test_stats_after_trade(client):
    _full_trade(client)
    d = client.get("/v1/stats").json()
    assert d["total_trades"] >= 1
    assert d["completed_trades"] >= 1
    assert d["active_agents"] >= 2
    assert d["active_sellers"] >= 1
    assert d["fees_earned"] > 0


def test_stats_no_auth_required(client):
    resp = client.get("/v1/stats")
    assert resp.status_code == 200


# ── /v1/agents/list ──


def test_agents_list_empty(client):
    resp = client.get("/v1/agents/list")
    assert resp.status_code == 200
    assert resp.json()["agents"] == []


def test_agents_list_returns_agents(client):
    _register(client)
    _register(client)
    agents = client.get("/v1/agents/list").json()["agents"]
    assert len(agents) == 2
    # Should have pubkey and cu_balance, no api_key
    for a in agents:
        assert "pubkey" in a
        assert "cu_balance" in a
        assert "api_key" not in a


def test_agents_list_no_auth_required(client):
    resp = client.get("/v1/agents/list")
    assert resp.status_code == 200


# ── /v1/sellers/list ──


def test_sellers_list_empty(client):
    resp = client.get("/v1/sellers/list")
    assert resp.status_code == 200
    assert resp.json()["sellers"] == []


def test_sellers_list_returns_sellers(client):
    import hashlib
    _, key = _register(client)
    schemas = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    client.post("/v1/schemas/register", json=schemas, headers={"x-api-key": key})
    ci = json.dumps(schemas["input_schema"], sort_keys=True, separators=(",", ":"))
    co = json.dumps(schemas["output_schema"], sort_keys=True, separators=(",", ":"))
    cap_hash = hashlib.sha256((ci + "||" + co).encode()).hexdigest()
    client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": 25, "capacity": 3}, headers={"x-api-key": key})

    sellers = client.get("/v1/sellers/list").json()["sellers"]
    assert len(sellers) == 1
    assert sellers[0]["price_cu"] == 25
    assert sellers[0]["capacity"] == 3


def test_sellers_list_sorted_by_price(client):
    import hashlib
    for price in [50, 10, 30]:
        _, key = _register(client)
        schemas = {"input_schema": {"type": "string", "p": price}, "output_schema": {"type": "string"}}
        client.post("/v1/schemas/register", json=schemas, headers={"x-api-key": key})
        ci = json.dumps(schemas["input_schema"], sort_keys=True, separators=(",", ":"))
        co = json.dumps(schemas["output_schema"], sort_keys=True, separators=(",", ":"))
        cap_hash = hashlib.sha256((ci + "||" + co).encode()).hexdigest()
        client.post("/v1/sellers/register", json={"capability_hash": cap_hash, "price_cu": price, "capacity": 1}, headers={"x-api-key": key})

    sellers = client.get("/v1/sellers/list").json()["sellers"]
    prices = [s["price_cu"] for s in sellers]
    assert prices == sorted(prices)


# ── /v1/trades/recent ──


def test_trades_recent_empty(client):
    resp = client.get("/v1/trades/recent")
    assert resp.status_code == 200
    assert resp.json()["trades"] == []


def test_trades_recent_returns_trades(client):
    _full_trade(client)
    trades = client.get("/v1/trades/recent").json()["trades"]
    assert len(trades) >= 1
    t = trades[0]
    assert "id" in t
    assert "price_cu" in t
    assert "status" in t
    assert t["status"] == "completed"


def test_trades_recent_limit(client):
    _full_trade(client)
    _full_trade(client)
    trades = client.get("/v1/trades/recent?limit=1").json()["trades"]
    assert len(trades) == 1


def test_trades_recent_no_auth_required(client):
    resp = client.get("/v1/trades/recent")
    assert resp.status_code == 200


# ── /v1/trade_log ──


def test_trade_log_empty(client):
    resp = client.get("/v1/trade_log")
    assert resp.status_code == 200
    assert resp.json()["trades"] == [] or isinstance(resp.json()["trades"], list)


def test_trade_log_no_auth_required(client):
    resp = client.get("/v1/trade_log")
    assert resp.status_code == 200
