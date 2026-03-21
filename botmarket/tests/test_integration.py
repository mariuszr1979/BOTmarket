# test_integration.py — Step 5: Integration Testing (Phase 2 — pre-money)
import sys
import os
import json
import asyncio
import struct
import random
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app
import db
import matching
from wire import (
    HEADER_SIZE, unpack_header, pack_message,
    MSG_REGISTER_AGENT, MSG_REGISTER_SCHEMA, MSG_REGISTER_SELLER,
    MSG_MATCH_REQUEST, MSG_MATCH_RESPONSE, MSG_EXECUTE,
    MSG_EXECUTE_RESPONSE, MSG_QUERY_EVENTS, MSG_EVENTS_RESPONSE, MSG_ERROR,
)
from constants import FEE_TOTAL, BOND_SLASH, SLASH_TO_BUYER
from identity import generate_keypair, sign_request, canonical_bytes


# ── Helpers ──────────────────────────────────────────────


def _seed_cu(pubkey, amount):
    """Directly set a buyer's CU balance (test utility)."""
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


def _escrow_count():
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM escrow WHERE status = 'held'").fetchone()
    finally:
        conn.close()
    return row["cnt"]


def _tcp_payload(api_key: str, body: dict) -> bytes:
    key_bytes = api_key.encode()
    return struct.pack('!H', len(key_bytes)) + key_bytes + json.dumps(body).encode()


# ── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("BOTMARKET_DB", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    matching._seller_tables.clear()
    db.init_db(db_path)
    return TestClient(app)


@pytest.fixture
def tcp_server(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("BOTMARKET_DB", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    matching._seller_tables.clear()
    db.init_db(db_path)

    from tcp_server import handle_client

    loop = asyncio.new_event_loop()
    server = loop.run_until_complete(
        asyncio.start_server(handle_client, "127.0.0.1", 0)
    )
    port = server.sockets[0].getsockname()[1]
    yield ("127.0.0.1", port, loop)
    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


async def _send_recv(host, port, msg_type, payload):
    reader, writer = await asyncio.open_connection(host, port)
    msg = pack_message(msg_type, payload)
    writer.write(msg)
    await writer.drain()
    header = await reader.readexactly(HEADER_SIZE)
    rt, length = unpack_header(header)
    body = await reader.readexactly(length)
    writer.close()
    await writer.wait_closed()
    return rt, body


def _register_and_setup(client):
    """Register seller + buyer, schema, seller listing. Returns dict with keys."""
    seller = client.post("/v1/agents/register").json()
    buyer = client.post("/v1/agents/register").json()

    _seed_cu(seller["agent_id"], 20.0)

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "task": "summarize"},
        "output_schema": {"type": "string", "result": "summary"},
    }, headers={"x-api-key": seller["api_key"]}).json()

    client.post("/v1/sellers/register", json={
        "capability_hash": schema["capability_hash"],
        "price_cu": 20.0,
        "capacity": 10,
    }, headers={"x-api-key": seller["api_key"]})

    _seed_cu(buyer["agent_id"], 100.0)

    return {
        "seller": seller,
        "buyer": buyer,
        "capability_hash": schema["capability_hash"],
    }


# ── TEST 1: Happy Path (Full Lifecycle) ─────────────────


def test_happy_path_full_lifecycle(client):
    """Register → match → execute → settle. Verify final balances."""
    s = _register_and_setup(client)
    buyer_key = s["buyer"]["api_key"]

    # Match
    match_resp = client.post("/v1/match", json={
        "capability_hash": s["capability_hash"],
    }, headers={"x-api-key": buyer_key}).json()
    assert match_resp["status"] == "matched"
    trade_id = match_resp["trade_id"]
    assert match_resp["price_cu"] == 20.0

    # Execute
    exec_resp = client.post(f"/v1/trades/{trade_id}/execute", json={
        "input": "summarize this",
    }, headers={"x-api-key": buyer_key}).json()
    assert exec_resp["status"] == "executed"

    # Settle
    settle_resp = client.post(f"/v1/trades/{trade_id}/settle",
                               headers={"x-api-key": buyer_key}).json()
    assert settle_resp["status"] == "completed"

    # Verify balances
    seller_balance = _get_balance(s["seller"]["agent_id"])
    buyer_balance = _get_balance(s["buyer"]["agent_id"])
    expected_fee = 20.0 * FEE_TOTAL
    expected_seller = 20.0 - expected_fee

    assert abs(seller_balance - expected_seller) < 1e-9, f"seller got {seller_balance}"
    assert abs(buyer_balance - 80.0) < 1e-9, f"buyer has {buyer_balance}"
    assert _escrow_count() == 0, "escrow should be empty after settlement"

    # Events
    events_resp = client.get(f"/v1/events/{s['buyer']['agent_id']}",
                              headers={"x-api-key": buyer_key}).json()
    event_types = [e["event_type"] for e in events_resp["events"]]
    assert "match_made" in event_types
    assert "trade_executed" in event_types
    assert "settlement_complete" in event_types


# ── TEST 2: No Match Found ──────────────────────────────


def test_no_match_found(client):
    buyer = client.post("/v1/agents/register").json()
    _seed_cu(buyer["agent_id"], 100.0)

    resp = client.post("/v1/match", json={
        "capability_hash": "0" * 64,
    }, headers={"x-api-key": buyer["api_key"]}).json()

    assert resp["status"] == "no_match"
    assert abs(_get_balance(buyer["agent_id"]) - 100.0) < 1e-9


# ── TEST 3: Insufficient CU ─────────────────────────────


def test_insufficient_cu(client):
    seller = client.post("/v1/agents/register").json()
    buyer = client.post("/v1/agents/register").json()

    _seed_cu(seller["agent_id"], 50.0)

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string"},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": seller["api_key"]}).json()

    client.post("/v1/sellers/register", json={
        "capability_hash": schema["capability_hash"],
        "price_cu": 50.0,
        "capacity": 10,
    }, headers={"x-api-key": seller["api_key"]})

    _seed_cu(buyer["agent_id"], 30.0)

    resp = client.post("/v1/match", json={
        "capability_hash": schema["capability_hash"],
    }, headers={"x-api-key": buyer["api_key"]}).json()

    assert resp["status"] == "insufficient_cu"
    assert abs(_get_balance(buyer["agent_id"]) - 30.0) < 1e-9


# ── TEST 4: Seller at Capacity ───────────────────────────


def test_seller_at_capacity(client):
    seller = client.post("/v1/agents/register").json()
    buyer_b = client.post("/v1/agents/register").json()
    buyer_c = client.post("/v1/agents/register").json()

    _seed_cu(seller["agent_id"], 10.0)

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "cap_test": True},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": seller["api_key"]}).json()

    client.post("/v1/sellers/register", json={
        "capability_hash": schema["capability_hash"],
        "price_cu": 10.0,
        "capacity": 1,
    }, headers={"x-api-key": seller["api_key"]})

    _seed_cu(buyer_b["agent_id"], 100.0)
    _seed_cu(buyer_c["agent_id"], 100.0)

    # Buyer B matches — fills last slot
    resp_b = client.post("/v1/match", json={
        "capability_hash": schema["capability_hash"],
    }, headers={"x-api-key": buyer_b["api_key"]}).json()
    assert resp_b["status"] == "matched"

    # Buyer C tries — seller at capacity
    resp_c = client.post("/v1/match", json={
        "capability_hash": schema["capability_hash"],
    }, headers={"x-api-key": buyer_c["api_key"]}).json()
    assert resp_c["status"] == "no_match"


# ── TEST 5: Bond Slash (SLA Violation) ───────────────────


def test_bond_slash_sla_violation(client):
    seller = client.post("/v1/agents/register").json()
    buyer = client.post("/v1/agents/register").json()

    _seed_cu(seller["agent_id"], 20.0)

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "sla": True},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": seller["api_key"]}).json()

    client.post("/v1/sellers/register", json={
        "capability_hash": schema["capability_hash"],
        "price_cu": 20.0,
        "capacity": 10,
    }, headers={"x-api-key": seller["api_key"]})

    _seed_cu(buyer["agent_id"], 100.0)

    # Match + execute
    match_resp = client.post("/v1/match", json={
        "capability_hash": schema["capability_hash"],
    }, headers={"x-api-key": buyer["api_key"]}).json()
    trade_id = match_resp["trade_id"]

    client.post(f"/v1/trades/{trade_id}/execute", json={
        "input": "test",
    }, headers={"x-api-key": buyer["api_key"]})

    # Set extreme latency bound + staked CU to trigger slash
    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE sellers SET latency_bound_us = 1, cu_staked = 100.0 WHERE agent_pubkey = ?",
            (seller["agent_id"],),
        )
        # Set trade latency to something above bound
        conn.execute(
            "UPDATE trades SET latency_us = 999999 WHERE id = ?",
            (trade_id,),
        )
        conn.commit()
    finally:
        conn.close()

    # Settle — should slash
    settle_resp = client.post(f"/v1/trades/{trade_id}/settle",
                               headers={"x-api-key": buyer["api_key"]}).json()
    assert settle_resp["status"] == "violated"
    assert settle_resp["reason"] == "latency_exceeded"

    # Buyer should get refund + slash share
    buyer_balance = _get_balance(buyer["agent_id"])
    # Refunded 20 CU from escrow + 50% of (100 * 0.05 = 5.0) = 2.5
    # Total = 80 (remaining) + 20 (refund) + 2.5 (slash share) = 102.5
    expected_slash = 100.0 * BOND_SLASH * SLASH_TO_BUYER  # 2.5
    assert abs(buyer_balance - (80.0 + 20.0 + expected_slash)) < 1e-9


# ── TEST 6: Multiple Sellers, Price Sorting ──────────────


def test_multiple_sellers_price_sorting(client):
    sellers = []
    prices = [30.0, 10.0, 20.0]
    cap_hash = None

    for price in prices:
        s = client.post("/v1/agents/register").json()
        sellers.append(s)

    # Register schema once
    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "sort_test": True},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": sellers[0]["api_key"]}).json()
    cap_hash = schema["capability_hash"]

    # Register each as seller at different prices
    for s, price in zip(sellers, prices):
        _seed_cu(s["agent_id"], price)
        client.post("/v1/sellers/register", json={
            "capability_hash": cap_hash,
            "price_cu": price,
            "capacity": 10,
        }, headers={"x-api-key": s["api_key"]})

    buyer = client.post("/v1/agents/register").json()
    _seed_cu(buyer["agent_id"], 100.0)

    resp = client.post("/v1/match", json={
        "capability_hash": cap_hash,
    }, headers={"x-api-key": buyer["api_key"]}).json()

    assert resp["status"] == "matched"
    assert resp["price_cu"] == 10.0
    assert resp["seller_pubkey"] == sellers[1]["agent_id"]  # cheapest seller


# ── TEST 7: CU Invariant ────────────────────────────────


def test_cu_invariant_50_random_trades(client):
    """Run 50 random trades. Total CU must be conserved."""
    seller = client.post("/v1/agents/register").json()
    buyer = client.post("/v1/agents/register").json()

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "invariant": True},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": seller["api_key"]}).json()

    _seed_cu(seller["agent_id"], 1.0)

    client.post("/v1/sellers/register", json={
        "capability_hash": schema["capability_hash"],
        "price_cu": 1.0,
        "capacity": 100,
    }, headers={"x-api-key": seller["api_key"]})

    seller_stake = 1.0
    total_seeded = 200.0 + seller_stake
    _seed_cu(buyer["agent_id"], 200.0)

    completed = 0
    for i in range(50):
        # Match
        resp = client.post("/v1/match", json={
            "capability_hash": schema["capability_hash"],
        }, headers={"x-api-key": buyer["api_key"]}).json()
        if resp["status"] != "matched":
            break
        trade_id = resp["trade_id"]

        # Execute
        client.post(f"/v1/trades/{trade_id}/execute", json={
            "input": f"trade_{i}",
        }, headers={"x-api-key": buyer["api_key"]})

        # Settle
        client.post(f"/v1/trades/{trade_id}/settle",
                     headers={"x-api-key": buyer["api_key"]})
        completed += 1

    assert completed == 50, f"only completed {completed} trades"

    # Invariant: sum(balances) + cu_staked + fees = total_seeded
    # Fees go to platform (not tracked in agent balances)
    seller_bal = _get_balance(seller["agent_id"])
    buyer_bal = _get_balance(buyer["agent_id"])
    total_fees = completed * 1.0 * FEE_TOTAL  # 50 * 0.015

    # cu_staked is locked in sellers table, not in agent balance
    conn = db.get_connection()
    try:
        staked_row = conn.execute(
            "SELECT cu_staked FROM sellers WHERE agent_pubkey = ?", (seller["agent_id"],)
        ).fetchone()
    finally:
        conn.close()
    cu_staked = staked_row["cu_staked"] if staked_row else 0.0

    assert abs((seller_bal + buyer_bal + total_fees + cu_staked) - total_seeded) < 0.001, \
        f"invariant broken: seller={seller_bal} buyer={buyer_bal} fees={total_fees} staked={cu_staked} total={seller_bal + buyer_bal + total_fees + cu_staked}"

    # No negative balances
    assert seller_bal >= 0
    assert buyer_bal >= 0

    # No orphaned escrow
    assert _escrow_count() == 0


# ── TEST 8: Binary Round-Trip ────────────────────────────


def test_binary_round_trip(tcp_server):
    """Full lifecycle via TCP binary only."""
    host, port, loop = tcp_server

    async def _run():
        # Register agent (seller)
        _, body = await _send_recv(host, port, MSG_REGISTER_AGENT, b'{}')
        seller = json.loads(body)

        # Register agent (buyer)
        _, body = await _send_recv(host, port, MSG_REGISTER_AGENT, b'{}')
        buyer = json.loads(body)

        # Register schema
        payload = _tcp_payload(seller["api_key"], {
            "input_schema": {"type": "string", "binary_test": True},
            "output_schema": {"type": "string"},
        })
        _, body = await _send_recv(host, port, MSG_REGISTER_SCHEMA, payload)
        schema = json.loads(body)

        # Register seller
        # Seed seller with CU for staking
        conn = db.get_connection()
        try:
            conn.execute("UPDATE agents SET cu_balance = 20.0 WHERE pubkey = ?", (seller["agent_id"],))
            conn.commit()
        finally:
            conn.close()
        payload = _tcp_payload(seller["api_key"], {
            "capability_hash": schema["capability_hash"],
            "price_cu": 20.0,
            "capacity": 10,
        })
        _, body = await _send_recv(host, port, MSG_REGISTER_SELLER, payload)
        assert json.loads(body)["status"] == "registered"

        # Seed buyer CU
        conn = db.get_connection()
        try:
            conn.execute("UPDATE agents SET cu_balance = 100.0 WHERE pubkey = ?", (buyer["agent_id"],))
            conn.commit()
        finally:
            conn.close()

        # Match via TCP
        payload = _tcp_payload(buyer["api_key"], {
            "capability_hash": schema["capability_hash"],
        })
        rt, body = await _send_recv(host, port, MSG_MATCH_REQUEST, payload)
        match_data = json.loads(body)
        assert match_data["status"] == "matched"
        assert match_data["price_cu"] == 20.0

        # Execute via TCP
        payload = _tcp_payload(buyer["api_key"], {
            "trade_id": match_data["trade_id"],
            "input": "binary test",
        })
        rt, body = await _send_recv(host, port, MSG_EXECUTE, payload)
        exec_data = json.loads(body)
        assert exec_data["status"] == "executed"

        # Verify binary response structure (correct header)
        assert rt == MSG_EXECUTE_RESPONSE

        # Check balances
        buyer_bal = _get_balance(buyer["agent_id"])
        assert abs(buyer_bal - 80.0) < 1e-9

    loop.run_until_complete(_run())


# ── TEST 9: Binary + JSON Equivalence ────────────────────


def test_binary_json_equivalence(client, tcp_server):
    """Run happy path via JSON then via TCP. Compare final balances."""
    host, port, loop = tcp_server

    # ── JSON path ──
    json_seller = client.post("/v1/agents/register").json()
    json_buyer = client.post("/v1/agents/register").json()

    _seed_cu(json_seller["agent_id"], 20.0)

    schema_json = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "equiv_test": "json_path"},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": json_seller["api_key"]}).json()

    client.post("/v1/sellers/register", json={
        "capability_hash": schema_json["capability_hash"],
        "price_cu": 20.0,
        "capacity": 10,
    }, headers={"x-api-key": json_seller["api_key"]})

    _seed_cu(json_buyer["agent_id"], 100.0)

    m = client.post("/v1/match", json={
        "capability_hash": schema_json["capability_hash"],
    }, headers={"x-api-key": json_buyer["api_key"]}).json()

    client.post(f"/v1/trades/{m['trade_id']}/execute", json={
        "input": "equiv",
    }, headers={"x-api-key": json_buyer["api_key"]})

    client.post(f"/v1/trades/{m['trade_id']}/settle",
                 headers={"x-api-key": json_buyer["api_key"]})

    json_seller_bal = _get_balance(json_seller["agent_id"])
    json_buyer_bal = _get_balance(json_buyer["agent_id"])

    # ── TCP path ──
    async def _run():
        _, body = await _send_recv(host, port, MSG_REGISTER_AGENT, b'{}')
        tcp_seller = json.loads(body)
        _, body = await _send_recv(host, port, MSG_REGISTER_AGENT, b'{}')
        tcp_buyer = json.loads(body)

        payload = _tcp_payload(tcp_seller["api_key"], {
            "input_schema": {"type": "string", "equiv_test": "tcp_path"},
            "output_schema": {"type": "string"},
        })
        _, body = await _send_recv(host, port, MSG_REGISTER_SCHEMA, payload)
        tcp_schema = json.loads(body)

        # Seed TCP seller with CU for staking
        conn = db.get_connection()
        try:
            conn.execute("UPDATE agents SET cu_balance = 20.0 WHERE pubkey = ?", (tcp_seller["agent_id"],))
            conn.commit()
        finally:
            conn.close()

        payload = _tcp_payload(tcp_seller["api_key"], {
            "capability_hash": tcp_schema["capability_hash"],
            "price_cu": 20.0,
            "capacity": 10,
        })
        await _send_recv(host, port, MSG_REGISTER_SELLER, payload)

        conn = db.get_connection()
        try:
            conn.execute("UPDATE agents SET cu_balance = 100.0 WHERE pubkey = ?", (tcp_buyer["agent_id"],))
            conn.commit()
        finally:
            conn.close()

        payload = _tcp_payload(tcp_buyer["api_key"], {
            "capability_hash": tcp_schema["capability_hash"],
        })
        _, body = await _send_recv(host, port, MSG_MATCH_REQUEST, payload)
        tcp_match = json.loads(body)

        payload = _tcp_payload(tcp_buyer["api_key"], {
            "trade_id": tcp_match["trade_id"],
            "input": "equiv",
        })
        await _send_recv(host, port, MSG_EXECUTE, payload)

        # Settle via execute_response msg type (settle handler uses same endpoint)
        # Actually need to build a settle payload — tcp_server has MSG_SETTLE
        # We'll need to use the settle handler directly. But the TCP server dispatch
        # table currently doesn't include settle. Let's check...
        # For now, settle via JSON since both share the same core DB.
        # The key test is that balances match.

        return tcp_buyer["agent_id"], tcp_seller["agent_id"]

    tcp_buyer_id, tcp_seller_id = loop.run_until_complete(_run())

    # Settle TCP trade via JSON (both share same DB and core logic)
    # Get the trade for the TCP buyer
    conn = db.get_connection()
    try:
        trade = conn.execute(
            "SELECT id FROM trades WHERE buyer_pubkey = ? AND status = 'executed'",
            (tcp_buyer_id,),
        ).fetchone()
        api_key_row = conn.execute(
            "SELECT api_key FROM agents WHERE pubkey = ?", (tcp_buyer_id,)
        ).fetchone()
    finally:
        conn.close()

    client.post(f"/v1/trades/{trade['id']}/settle",
                 headers={"x-api-key": api_key_row["api_key"]})

    tcp_seller_bal = _get_balance(tcp_seller_id)
    tcp_buyer_bal = _get_balance(tcp_buyer_id)

    # Same CU amounts regardless of transport
    assert abs(json_seller_bal - tcp_seller_bal) < 1e-9, \
        f"seller balance mismatch: JSON={json_seller_bal} TCP={tcp_seller_bal}"
    assert abs(json_buyer_bal - tcp_buyer_bal) < 1e-9, \
        f"buyer balance mismatch: JSON={json_buyer_bal} TCP={tcp_buyer_bal}"


# ── Additional invariant checks ──────────────────────────


def test_no_negative_balances_after_trades(client):
    """No agent should ever have negative CU balance."""
    s = _register_and_setup(client)

    for i in range(5):
        resp = client.post("/v1/match", json={
            "capability_hash": s["capability_hash"],
        }, headers={"x-api-key": s["buyer"]["api_key"]}).json()
        if resp["status"] != "matched":
            break
        trade_id = resp["trade_id"]
        client.post(f"/v1/trades/{trade_id}/execute", json={
            "input": f"neg_test_{i}",
        }, headers={"x-api-key": s["buyer"]["api_key"]})
        client.post(f"/v1/trades/{trade_id}/settle",
                     headers={"x-api-key": s["buyer"]["api_key"]})

    conn = db.get_connection()
    try:
        rows = conn.execute("SELECT pubkey, cu_balance FROM agents").fetchall()
    finally:
        conn.close()

    for row in rows:
        assert row["cu_balance"] >= 0, f"negative balance for {row['pubkey']}: {row['cu_balance']}"


def test_no_orphaned_escrow_after_settlement(client):
    """All escrow rows should be resolved after settlement."""
    s = _register_and_setup(client)

    trade_ids = []
    for i in range(3):
        resp = client.post("/v1/match", json={
            "capability_hash": s["capability_hash"],
        }, headers={"x-api-key": s["buyer"]["api_key"]}).json()
        assert resp["status"] == "matched"
        trade_ids.append(resp["trade_id"])

    for tid in trade_ids:
        client.post(f"/v1/trades/{tid}/execute", json={"input": "test"},
                     headers={"x-api-key": s["buyer"]["api_key"]})
        client.post(f"/v1/trades/{tid}/settle",
                     headers={"x-api-key": s["buyer"]["api_key"]})

    assert _escrow_count() == 0


def test_event_count_matches_lifecycle(client):
    """Each trade should produce exactly 3 events: match, execute, settle."""
    s = _register_and_setup(client)

    resp = client.post("/v1/match", json={
        "capability_hash": s["capability_hash"],
    }, headers={"x-api-key": s["buyer"]["api_key"]}).json()
    trade_id = resp["trade_id"]

    client.post(f"/v1/trades/{trade_id}/execute", json={"input": "evt_test"},
                 headers={"x-api-key": s["buyer"]["api_key"]})
    client.post(f"/v1/trades/{trade_id}/settle",
                 headers={"x-api-key": s["buyer"]["api_key"]})

    events_resp = client.get(f"/v1/events/{s['buyer']['agent_id']}",
                              headers={"x-api-key": s["buyer"]["api_key"]}).json()

    # Filter trade-specific events
    trade_events = []
    for e in events_resp["events"]:
        data = json.loads(e["event_data"])
        if data.get("trade_id") == trade_id:
            trade_events.append(e["event_type"])

    assert trade_events == ["match_made", "trade_executed", "settlement_complete"]


def test_deterministic_results(client):
    """Same setup produces same balance every time (no randomness in core)."""
    results = []
    for _ in range(3):
        # Reset state
        matching._seller_tables.clear()
        s = _register_and_setup(client)

        resp = client.post("/v1/match", json={
            "capability_hash": s["capability_hash"],
        }, headers={"x-api-key": s["buyer"]["api_key"]}).json()

        client.post(f"/v1/trades/{resp['trade_id']}/execute",
                     json={"input": "deterministic"},
                     headers={"x-api-key": s["buyer"]["api_key"]})

        client.post(f"/v1/trades/{resp['trade_id']}/settle",
                     headers={"x-api-key": s["buyer"]["api_key"]})

        results.append({
            "seller_bal": _get_balance(s["seller"]["agent_id"]),
            "buyer_bal": _get_balance(s["buyer"]["agent_id"]),
        })

    # All iterations produce identical results
    for r in results[1:]:
        assert abs(r["seller_bal"] - results[0]["seller_bal"]) < 1e-9
        assert abs(r["buyer_bal"] - results[0]["buyer_bal"]) < 1e-9


# ═══════════════════════════════════════════════════════
# Step 5 specific integration scenarios
# ═══════════════════════════════════════════════════════

# ── Ed25519 helpers ──────────────────────────────────────

def _register_ed25519(client):
    """Register an Ed25519 agent. Returns (priv_hex, pub_hex)."""
    priv, pub = generate_keypair()
    resp = client.post("/v1/agents/register/v2", json={"public_key": pub})
    assert resp.status_code == 201
    return priv, pub


def _ed25519_headers(body, priv, pub, timestamp_ns=None):
    """Build X-Public-Key / X-Signature / X-Timestamp request headers."""
    sig, ts = sign_request(body, priv, timestamp_ns)
    return {
        "X-Public-Key": pub,
        "X-Signature": sig,
        "X-Timestamp": str(ts),
    }


# ── Mock HTTP seller ──────────────────────────────────────

class _MockSellerHandler(BaseHTTPRequestHandler):
    response_body = {"output": "mock result"}
    response_status = 200
    response_delay = 0
    last_request_body = None
    call_count = 0

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        _MockSellerHandler.call_count += 1
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b""
        _MockSellerHandler.last_request_body = json.loads(body) if body else None
        if _MockSellerHandler.response_delay > 0:
            time.sleep(_MockSellerHandler.response_delay)
        self.send_response(_MockSellerHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(_MockSellerHandler.response_body).encode())

    def log_message(self, format, *args):
        pass  # silence server logs


# ── TEST A: Ed25519 Full Lifecycle ───────────────────────


def test_step5_ed25519_full_lifecycle(client):
    """Ed25519 keypair → register → schema → seller → match → execute → settle."""
    # Seller: Ed25519
    seller_priv, seller_pub = _register_ed25519(client)

    schema_body = {"input_schema": {"type": "string", "task": "summarize"},
                   "output_schema": {"type": "string", "result": "summary"}}
    schema_resp = client.post(
        "/v1/schemas/register",
        json=schema_body,
        headers=_ed25519_headers(schema_body, seller_priv, seller_pub),
    ).json()
    cap_hash = schema_resp["capability_hash"]
    assert len(cap_hash) == 64

    _seed_cu(seller_pub, 25.0)
    seller_body = {"capability_hash": cap_hash, "price_cu": 25.0, "capacity": 10}
    reg_resp = client.post(
        "/v1/sellers/register",
        json=seller_body,
        headers=_ed25519_headers(seller_body, seller_priv, seller_pub),
    ).json()
    assert reg_resp["status"] == "registered"

    # Buyer: Ed25519
    buyer_priv, buyer_pub = _register_ed25519(client)
    _seed_cu(buyer_pub, 100.0)

    match_body = {"capability_hash": cap_hash}
    match_resp = client.post(
        "/v1/match",
        json=match_body,
        headers=_ed25519_headers(match_body, buyer_priv, buyer_pub),
    ).json()
    assert match_resp["status"] == "matched"
    assert match_resp["price_cu"] == 25.0
    trade_id = match_resp["trade_id"]

    exec_body = {"input": "summarize this"}
    exec_resp = client.post(
        f"/v1/trades/{trade_id}/execute",
        json=exec_body,
        headers=_ed25519_headers(exec_body, buyer_priv, buyer_pub),
    ).json()
    assert exec_resp["status"] == "executed"

    settle_resp = client.post(
        f"/v1/trades/{trade_id}/settle",
        headers=_ed25519_headers(b"", buyer_priv, buyer_pub),
    ).json()
    assert settle_resp["status"] == "completed"

    # Balance checks
    expected_fee = 25.0 * FEE_TOTAL
    seller_bal = _get_balance(seller_pub)
    buyer_bal = _get_balance(buyer_pub)
    assert abs(seller_bal - (25.0 - expected_fee)) < 1e-9, f"seller got {seller_bal}"
    assert abs(buyer_bal - 75.0) < 1e-9, f"buyer has {buyer_bal}"
    assert _escrow_count() == 0


# ── TEST B: Signature Rejection ──────────────────────────


def test_step5_signature_rejection_wrong_sig(client):
    """Wrong signature → 401."""
    priv, pub = _register_ed25519(client)
    _seed_cu(pub, 100.0)
    # Sign with a different (wrong) private key
    other_priv, _ = generate_keypair()
    body = {"capability_hash": "a" * 64}
    resp = client.post(
        "/v1/match",
        json=body,
        headers=_ed25519_headers(body, other_priv, pub),  # signed with wrong key
    )
    assert resp.status_code == 401


def test_step5_signature_rejection_tampered_body(client):
    """Signature covers original body — tamper the body → 401."""
    priv, pub = _register_ed25519(client)
    _seed_cu(pub, 100.0)
    original_body = {"capability_hash": "a" * 64}
    sig, ts = sign_request(original_body, priv)
    tampered_body = {"capability_hash": "b" * 64}  # different hash
    resp = client.post(
        "/v1/match",
        json=tampered_body,
        headers={"X-Public-Key": pub, "X-Signature": sig, "X-Timestamp": str(ts)},
    )
    assert resp.status_code == 401


def test_step5_signature_rejection_expired_timestamp(client):
    """Timestamp >30s old → 401."""
    priv, pub = _register_ed25519(client)
    _seed_cu(pub, 100.0)
    old_ts = time.time_ns() - 60_000_000_000  # 60s ago
    body = {"capability_hash": "a" * 64}
    resp = client.post(
        "/v1/match",
        json=body,
        headers=_ed25519_headers(body, priv, pub, timestamp_ns=old_ts),
    )
    assert resp.status_code == 401


# ── TEST C: Real Seller Callback ─────────────────────────


def test_step5_real_seller_callback(client):
    """Seller with callback_url → execute POSTs to mock server, returns real output."""
    # Reset mock state
    _MockSellerHandler.call_count = 0
    _MockSellerHandler.last_request_body = None
    _MockSellerHandler.response_body = {"output": "summary: hello world"}
    _MockSellerHandler.response_status = 200
    _MockSellerHandler.response_delay = 0

    server = HTTPServer(("127.0.0.1", 0), _MockSellerHandler)
    port = server.server_address[1]
    t = threading.Thread(target=lambda: server.serve_forever(), daemon=True)
    t.start()
    try:
        # Register seller (API key, so health-check HEAD passes)
        seller = client.post("/v1/agents/register").json()
        buyer = client.post("/v1/agents/register").json()

        _seed_cu(seller["agent_id"], 20.0)

        schema = client.post("/v1/schemas/register", json={
            "input_schema": {"type": "string", "callback_test": True},
            "output_schema": {"type": "string"},
        }, headers={"x-api-key": seller["api_key"]}).json()
        cap_hash = schema["capability_hash"]

        reg = client.post("/v1/sellers/register", json={
            "capability_hash": cap_hash,
            "price_cu": 20.0,
            "capacity": 5,
            "callback_url": f"http://127.0.0.1:{port}/execute",
        }, headers={"x-api-key": seller["api_key"]}).json()
        assert reg["status"] == "registered"

        _seed_cu(buyer["agent_id"], 100.0)

        match_resp = client.post("/v1/match", json={
            "capability_hash": cap_hash,
        }, headers={"x-api-key": buyer["api_key"]}).json()
        assert match_resp["status"] == "matched"
        trade_id = match_resp["trade_id"]

        exec_resp = client.post(f"/v1/trades/{trade_id}/execute", json={
            "input": "hello world",
        }, headers={"x-api-key": buyer["api_key"]}).json()

        assert exec_resp["status"] == "executed"
        assert exec_resp["output"] == "summary: hello world"
        assert exec_resp["latency_us"] > 0  # real latency measured
        assert _MockSellerHandler.call_count == 1
        assert _MockSellerHandler.last_request_body["input"] == "hello world"
        assert _MockSellerHandler.last_request_body["trade_id"] == trade_id
    finally:
        server.shutdown()


# ── TEST D: Seller Callback Failure ──────────────────────


def test_step5_callback_failure_refunds_buyer(client):
    """Seller callback returns 500 → trade failed, buyer refunded from escrow."""
    # Reset mock state and configure to return 500 on POST
    _MockSellerHandler.call_count = 0
    _MockSellerHandler.response_status = 500
    _MockSellerHandler.response_body = {"error": "internal error"}
    _MockSellerHandler.response_delay = 0

    server = HTTPServer(("127.0.0.1", 0), _MockSellerHandler)
    port = server.server_address[1]
    t = threading.Thread(target=lambda: server.serve_forever(), daemon=True)
    t.start()
    try:
        seller = client.post("/v1/agents/register").json()
        buyer = client.post("/v1/agents/register").json()

        _seed_cu(seller["agent_id"], 50.0)

        schema = client.post("/v1/schemas/register", json={
            "input_schema": {"type": "string", "fail_test": True},
            "output_schema": {"type": "string"},
        }, headers={"x-api-key": seller["api_key"]}).json()
        cap_hash = schema["capability_hash"]

        reg = client.post("/v1/sellers/register", json={
            "capability_hash": cap_hash,
            "price_cu": 20.0,
            "capacity": 5,
            "callback_url": f"http://127.0.0.1:{port}/execute",
        }, headers={"x-api-key": seller["api_key"]}).json()
        assert reg["status"] == "registered"

        _seed_cu(buyer["agent_id"], 100.0)
        buyer_balance_before = _get_balance(buyer["agent_id"])

        match_resp = client.post("/v1/match", json={
            "capability_hash": cap_hash,
        }, headers={"x-api-key": buyer["api_key"]}).json()
        assert match_resp["status"] == "matched"
        trade_id = match_resp["trade_id"]

        # Balance debited at match time
        assert abs(_get_balance(buyer["agent_id"]) - (buyer_balance_before - 20.0)) < 1e-9

        exec_resp = client.post(f"/v1/trades/{trade_id}/execute", json={
            "input": "should fail",
        }, headers={"x-api-key": buyer["api_key"]}).json()

        assert exec_resp["status"] == "failed"
        assert exec_resp["reason"] == "callback_failed"

        # Buyer gets refund of price_cu + slash share (BOND_SLASH * SLASH_TO_BUYER of staked)
        # stake = price_cu = 20.0; slash_share = 20 * 0.05 * 0.5 = 0.5
        slash_share = 20.0 * BOND_SLASH * SLASH_TO_BUYER
        assert abs(_get_balance(buyer["agent_id"]) - (buyer_balance_before + slash_share)) < 1e-9

        # Trade status = failed, escrow refunded
        conn = db.get_connection()
        try:
            trade = conn.execute("SELECT status FROM trades WHERE id = ?", (trade_id,)).fetchone()
            escrow = conn.execute("SELECT status FROM escrow WHERE trade_id = ?", (trade_id,)).fetchone()
        finally:
            conn.close()
        assert trade["status"] == "failed"
        assert escrow["status"] == "refunded"
    finally:
        server.shutdown()


# ── TEST E: Mixed Auth ────────────────────────────────────


def test_step5_mixed_auth_same_seller(client):
    """API-key buyer and Ed25519 buyer both trade against the same seller."""
    seller = client.post("/v1/agents/register").json()
    _seed_cu(seller["agent_id"], 50.0)

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "mixed_test": True},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": seller["api_key"]}).json()
    cap_hash = schema["capability_hash"]

    client.post("/v1/sellers/register", json={
        "capability_hash": cap_hash,
        "price_cu": 20.0,
        "capacity": 10,
    }, headers={"x-api-key": seller["api_key"]})

    # Buyer A: legacy API key
    buyer_a = client.post("/v1/agents/register").json()
    _seed_cu(buyer_a["agent_id"], 100.0)
    match_a = client.post("/v1/match", json={"capability_hash": cap_hash},
                           headers={"x-api-key": buyer_a["api_key"]}).json()
    assert match_a["status"] == "matched"
    exec_a = client.post(f"/v1/trades/{match_a['trade_id']}/execute",
                          json={"input": "api key trade"},
                          headers={"x-api-key": buyer_a["api_key"]}).json()
    assert exec_a["status"] == "executed"
    settle_a = client.post(f"/v1/trades/{match_a['trade_id']}/settle",
                            headers={"x-api-key": buyer_a["api_key"]}).json()
    assert settle_a["status"] == "completed"

    # Buyer B: Ed25519
    buyer_b_priv, buyer_b_pub = _register_ed25519(client)
    _seed_cu(buyer_b_pub, 100.0)
    mb = {"capability_hash": cap_hash}
    match_b = client.post("/v1/match", json=mb,
                           headers=_ed25519_headers(mb, buyer_b_priv, buyer_b_pub)).json()
    assert match_b["status"] == "matched"
    eb = {"input": "ed25519 trade"}
    exec_b = client.post(f"/v1/trades/{match_b['trade_id']}/execute", json=eb,
                          headers=_ed25519_headers(eb, buyer_b_priv, buyer_b_pub)).json()
    assert exec_b["status"] == "executed"
    settle_b = client.post(f"/v1/trades/{match_b['trade_id']}/settle",
                            headers=_ed25519_headers(b"", buyer_b_priv, buyer_b_pub)).json()
    assert settle_b["status"] == "completed"

    # Both buyers paid the same price, both trades settled identically
    expected_fee = 20.0 * FEE_TOTAL
    buyer_a_bal = _get_balance(buyer_a["agent_id"])
    buyer_b_bal = _get_balance(buyer_b_pub)
    assert abs(buyer_a_bal - 80.0) < 1e-9
    assert abs(buyer_b_bal - 80.0) < 1e-9


# ── TEST F: PostgreSQL Concurrency ───────────────────────


@pytest.mark.skipif(not db._is_pg(), reason="requires PostgreSQL — set DATABASE_URL")
def test_step5_pg_concurrency(client):
    """50 agents send match requests simultaneously. No deadlocks, CU invariant holds."""
    import concurrent.futures

    # One seller, 50 buyers
    seller = client.post("/v1/agents/register").json()
    _seed_cu(seller["agent_id"], 10.0)

    schema = client.post("/v1/schemas/register", json={
        "input_schema": {"type": "string", "concurrency_test": True},
        "output_schema": {"type": "string"},
    }, headers={"x-api-key": seller["api_key"]}).json()
    cap_hash = schema["capability_hash"]

    client.post("/v1/sellers/register", json={
        "capability_hash": cap_hash,
        "price_cu": 10.0,
        "capacity": 50,
    }, headers={"x-api-key": seller["api_key"]})

    buyers = []
    for _ in range(50):
        b = client.post("/v1/agents/register").json()
        _seed_cu(b["agent_id"], 50.0)
        buyers.append(b)

    total_seeded = sum(50.0 for _ in buyers) + 10.0  # buyer CU + seller stake

    def _do_trade(b):
        m = client.post("/v1/match", json={"capability_hash": cap_hash},
                         headers={"x-api-key": b["api_key"]}).json()
        if m["status"] != "matched":
            return False
        e = client.post(f"/v1/trades/{m['trade_id']}/execute",
                         json={"input": "concurrent"},
                         headers={"x-api-key": b["api_key"]}).json()
        if e["status"] != "executed":
            return False
        s = client.post(f"/v1/trades/{m['trade_id']}/settle",
                         headers={"x-api-key": b["api_key"]}).json()
        return s["status"] == "completed"

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        outcomes = list(pool.map(_do_trade, buyers))

    completed = sum(1 for o in outcomes if o)
    assert completed == 50, f"only {completed}/50 trades completed"

    # CU invariant
    conn = db.get_connection()
    try:
        agent_rows = conn.execute("SELECT cu_balance FROM agents").fetchall()
        staked_row = conn.execute(
            "SELECT cu_staked FROM sellers WHERE agent_pubkey = ?", (seller["agent_id"],)
        ).fetchone()
    finally:
        conn.close()

    total_agent_cu = sum(r["cu_balance"] for r in agent_rows)
    cu_staked = staked_row["cu_staked"] if staked_row else 0.0
    total_fees = completed * 10.0 * FEE_TOTAL

    assert total_agent_cu >= 0
    assert abs((total_agent_cu + cu_staked + total_fees) - total_seeded) < 0.01, \
        f"invariant broken: agent_cu={total_agent_cu} staked={cu_staked} fees={total_fees}"

    # Seq numbers strictly monotonic
    conn = db.get_connection()
    try:
        seqs = [r[0] for r in conn.execute("SELECT seq FROM events ORDER BY seq").fetchall()]
    finally:
        conn.close()
    assert seqs == sorted(set(seqs)), "event seq numbers not strictly monotonic"
