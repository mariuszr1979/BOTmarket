# test_lifecycle.py — End-to-end trade lifecycle tests
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app
import db
from matching import clear_tables
from constants import FEE_TOTAL, BOND_SLASH, SLASH_TO_BUYER


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BOTMARKET_DB", str(tmp_path / "test.db"))
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db().close()
    clear_tables()
    return TestClient(app)


def _seed_cu(pubkey, amount):
    conn = db.get_connection()
    try:
        conn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?", (amount, pubkey))
        conn.commit()
    finally:
        conn.close()


def _get_balance(pubkey):
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (pubkey,)).fetchone()
    finally:
        conn.close()
    return row["cu_balance"]


def _register_agent(client):
    r = client.post("/v1/agents/register")
    assert r.status_code in (200, 201)
    return r.json()


def _register_schema(client, api_key):
    r = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "task": "lifecycle_test"},
        "output_schema": {"type": "string", "result": "output"},
    }, headers={"x-api-key": api_key})
    assert r.status_code in (200, 201)
    return r.json()["capability_hash"]


def _register_seller(client, api_key, cap_hash, price_cu=10.0):
    r = client.post("/v1/sellers/register", json={
        "capability_hash": cap_hash,
        "price_cu": price_cu,
        "capacity": 5,
    }, headers={"x-api-key": api_key})
    assert r.status_code in (200, 201)
    return r.json()


# ── Happy path ────────────────────────────────────────────────────────────────

def test_full_lifecycle_register_to_settle(client):
    """Register seller + buyer, match, execute, settle. Verify CU flow."""
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0

    # Seed seller stake CU
    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)

    # Seed buyer
    _seed_cu(buyer["agent_id"], 100.0)

    # Match
    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    match = r.json()
    assert match["status"] == "matched"
    trade_id = match["trade_id"]

    # Buyer CU should be reduced
    assert abs(_get_balance(buyer["agent_id"]) - (100.0 - price_cu)) < 1e-9

    # Execute
    r = client.post(f"/v1/trades/{trade_id}/execute",
                    json={"input": "hello"},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    assert r.json()["status"] == "executed"

    # Settle
    r = client.post(f"/v1/trades/{trade_id}/settle",
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    resp = r.json()
    assert resp["status"] == "completed"
    expected_seller = price_cu * (1.0 - FEE_TOTAL)
    assert abs(resp["seller_receives"] - expected_seller) < 1e-9
    assert abs(resp["fee_cu"] - price_cu * FEE_TOTAL) < 1e-9

    # Seller balance should reflect earnings
    assert abs(_get_balance(seller["agent_id"]) - expected_seller) < 1e-9


def test_buyer_cu_deducted_at_match(client):
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 20.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 50.0)

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    assert abs(_get_balance(buyer["agent_id"]) - 30.0) < 1e-9


def test_match_fails_insufficient_cu(client):
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 50.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 1.0)  # not enough

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    assert r.json()["status"] == "insufficient_cu"


def test_cannot_execute_same_trade_twice(client):
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    trade_id = r.json()["trade_id"]

    r1 = client.post(f"/v1/trades/{trade_id}/execute", json={"input": "x"},
                     headers={"x-api-key": buyer["api_key"]})
    assert r1.status_code == 200
    assert r1.json()["status"] == "executed"

    r2 = client.post(f"/v1/trades/{trade_id}/execute", json={"input": "x"},
                     headers={"x-api-key": buyer["api_key"]})
    assert r2.status_code == 400


def test_cannot_settle_before_execute(client):
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    trade_id = r.json()["trade_id"]

    r = client.post(f"/v1/trades/{trade_id}/settle",
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 400


def test_non_buyer_cannot_execute(client):
    seller = _register_agent(client)
    buyer = _register_agent(client)
    other = _register_agent(client)
    price_cu = 10.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    trade_id = r.json()["trade_id"]

    r = client.post(f"/v1/trades/{trade_id}/execute", json={"input": "x"},
                    headers={"x-api-key": other["api_key"]})
    assert r.status_code == 403


# ── Self-trade prevention ─────────────────────────────────────────────────────

def test_self_trade_returns_no_match(client):
    """An agent who is both buyer and seller should NOT match with itself."""
    agent = _register_agent(client)
    price_cu = 10.0
    _seed_cu(agent["agent_id"], 200.0)

    cap_hash = _register_schema(client, agent["api_key"])
    _register_seller(client, agent["api_key"], cap_hash, price_cu)

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": agent["api_key"]})
    assert r.status_code == 200
    assert r.json()["status"] == "no_match"


def test_self_trade_skips_to_other_seller(client):
    """If cheapest seller is the buyer, match should return next seller."""
    agent_a = _register_agent(client)
    agent_b = _register_agent(client)
    _seed_cu(agent_a["agent_id"], 200.0)
    _seed_cu(agent_b["agent_id"], 200.0)

    cap_hash = _register_schema(client, agent_a["api_key"])
    _register_seller(client, agent_a["api_key"], cap_hash, price_cu=5.0)
    _register_seller(client, agent_b["api_key"], cap_hash, price_cu=10.0)

    # agent_a tries to buy — should skip itself (5 CU) and get agent_b (10 CU)
    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": agent_a["api_key"]})
    assert r.status_code == 200
    match = r.json()
    assert match["status"] == "matched"
    assert match["seller_pubkey"] == agent_b["agent_id"]
    assert match["price_cu"] == 10.0


# ── Escrow timeout ────────────────────────────────────────────────────────────

def test_sweep_escrow_refunds_stale_executed_trade(client):
    """Executed trade older than ESCROW_TIMEOUT_NS should be auto-refunded."""
    import time
    from main import sweep_stale_escrow
    from constants import ESCROW_TIMEOUT_NS

    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    # Match + execute
    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    trade_id = r.json()["trade_id"]
    r = client.post(f"/v1/trades/{trade_id}/execute", json={"input": "test"},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.json()["status"] == "executed"

    buyer_balance_after_match = _get_balance(buyer["agent_id"])

    # Manually backdate the trade end_ns to simulate timeout
    conn = db.get_connection()
    try:
        old_end_ns = time.time_ns() - ESCROW_TIMEOUT_NS - 1_000_000_000  # 1s past timeout
        conn.execute("UPDATE trades SET end_ns = ? WHERE id = ?", (old_end_ns, trade_id))
        conn.commit()

        refunded = sweep_stale_escrow(conn)
    finally:
        conn.close()

    assert len(refunded) == 1
    assert refunded[0]["trade_id"] == trade_id
    assert refunded[0]["refunded_cu"] == price_cu

    # Buyer should get refund
    assert abs(_get_balance(buyer["agent_id"]) - (buyer_balance_after_match + price_cu)) < 1e-9

    # Trade status should be 'expired'
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT status FROM trades WHERE id = ?", (trade_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "expired"


def test_sweep_escrow_ignores_recent_executed_trade(client):
    """Executed trade within timeout should NOT be swept."""
    from main import sweep_stale_escrow

    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0

    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    trade_id = r.json()["trade_id"]
    r = client.post(f"/v1/trades/{trade_id}/execute", json={"input": "test"},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.json()["status"] == "executed"

    # Sweep immediately — should NOT refund (within timeout)
    conn = db.get_connection()
    try:
        refunded = sweep_stale_escrow(conn)
    finally:
        conn.close()

    assert len(refunded) == 0


def test_admin_sweep_endpoint(client):
    """POST /v1/admin/sweep-escrow should work with auth."""
    agent = _register_agent(client)
    r = client.post("/v1/admin/sweep-escrow",
                    headers={"x-api-key": agent["api_key"]})
    assert r.status_code == 200
    assert r.json()["swept"] == 0


# ── Quality score at settlement ───────────────────────────────────────────────

def _do_trade(client, buyer, seller, cap_hash):
    """Helper: match + execute a trade, return trade_id."""
    r = client.post("/v1/match", json={"capability_hash": cap_hash},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.json()["status"] == "matched"
    trade_id = r.json()["trade_id"]
    r = client.post(f"/v1/trades/{trade_id}/execute", json={"input": "test"},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.json()["status"] == "executed"
    return trade_id


def test_settle_with_quality_score(client):
    """Buyer can submit optional quality_score at settlement."""
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0
    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    trade_id = _do_trade(client, buyer, seller, cap_hash)

    r = client.post(f"/v1/trades/{trade_id}/settle",
                    json={"quality_score": 0.85},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    resp = r.json()
    assert resp["status"] == "completed"
    assert resp["quality_score"] == 0.85

    # Verify stored in DB
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT quality_score FROM trades WHERE id = ?",
                           (trade_id,)).fetchone()
    finally:
        conn.close()
    assert abs(row["quality_score"] - 0.85) < 1e-9


def test_settle_without_quality_score(client):
    """Settlement without quality_score still works (backward compatible)."""
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0
    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    trade_id = _do_trade(client, buyer, seller, cap_hash)

    r = client.post(f"/v1/trades/{trade_id}/settle",
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert "quality_score" not in r.json()


def test_settle_quality_score_out_of_range(client):
    """quality_score must be between 0.0 and 1.0."""
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0
    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    trade_id = _do_trade(client, buyer, seller, cap_hash)

    r = client.post(f"/v1/trades/{trade_id}/settle",
                    json={"quality_score": 1.5},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 400


def test_settle_quality_score_negative_rejected(client):
    """Negative quality_score is rejected."""
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0
    _seed_cu(seller["agent_id"], price_cu)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 100.0)

    trade_id = _do_trade(client, buyer, seller, cap_hash)

    r = client.post(f"/v1/trades/{trade_id}/settle",
                    json={"quality_score": -0.1},
                    headers={"x-api-key": buyer["api_key"]})
    assert r.status_code == 400


def test_leaderboard_shows_quality(client):
    """Leaderboard includes avg_quality and quality_votes."""
    seller = _register_agent(client)
    buyer = _register_agent(client)
    price_cu = 10.0
    _seed_cu(seller["agent_id"], price_cu * 3)
    cap_hash = _register_schema(client, seller["api_key"])
    _register_seller(client, seller["api_key"], cap_hash, price_cu)
    _seed_cu(buyer["agent_id"], 1000.0)

    # Trade 1: quality 0.8
    tid1 = _do_trade(client, buyer, seller, cap_hash)
    client.post(f"/v1/trades/{tid1}/settle",
                json={"quality_score": 0.8},
                headers={"x-api-key": buyer["api_key"]})

    # Trade 2: quality 0.6
    tid2 = _do_trade(client, buyer, seller, cap_hash)
    client.post(f"/v1/trades/{tid2}/settle",
                json={"quality_score": 0.6},
                headers={"x-api-key": buyer["api_key"]})

    # Trade 3: no quality
    tid3 = _do_trade(client, buyer, seller, cap_hash)
    client.post(f"/v1/trades/{tid3}/settle",
                headers={"x-api-key": buyer["api_key"]})

    r = client.get("/v1/leaderboard")
    assert r.status_code == 200
    entries = r.json()["leaderboard"]
    assert len(entries) == 1
    assert entries[0]["quality_votes"] == 2
    assert abs(entries[0]["avg_quality"] - 0.7) < 1e-3  # (0.8 + 0.6) / 2

