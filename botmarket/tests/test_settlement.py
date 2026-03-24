# test_settlement.py — Settlement/CU ledger unit tests
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from db import init_db
from settlement import settle_trade, slash_bond, maybe_set_sla, check_sla_decoherence
from constants import FEE_TOTAL, BOND_SLASH, SLASH_TO_BUYER, SLA_SAMPLE_SIZE


def _setup(price_cu=100.0, cu_staked=50.0, cu_balance_buyer=0.0, cu_balance_seller=0.0):
    """Create an in-memory DB with one trade ready for settlement."""
    conn = init_db(":memory:")
    now_ns = time.time_ns()
    conn.execute(
        "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, ?, ?)",
        ("buyer", "bkey", cu_balance_buyer, now_ns),
    )
    conn.execute(
        "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, ?, ?)",
        ("seller", "skey", cu_balance_seller, now_ns),
    )
    conn.execute(
        "INSERT INTO schemas (capability_hash, input_schema, output_schema, registered_at) VALUES (?, ?, ?, ?)",
        ("cap123", '{}', '{}', now_ns),
    )
    conn.execute(
        "INSERT INTO sellers (agent_pubkey, capability_hash, price_cu, latency_bound_us, capacity, "
        "active_calls, cu_staked, callback_url, sla_set_at_ns, registered_at_ns) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("seller", "cap123", price_cu, 0, 5, 0, cu_staked, None, None, now_ns),
    )
    conn.execute(
        "INSERT INTO trades (id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, start_ns, "
        "end_ns, status, latency_us) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("trade1", "buyer", "seller", "cap123", price_cu, now_ns, now_ns + 1_000_000, "executed", 1000),
    )
    conn.execute(
        "INSERT INTO escrow (trade_id, buyer_pubkey, seller_pubkey, cu_amount, status) VALUES (?, ?, ?, ?, ?)",
        ("trade1", "buyer", "seller", price_cu, "held"),
    )
    conn.commit()
    return conn


def _trade(conn):
    return dict(conn.execute("SELECT * FROM trades WHERE id = 'trade1'").fetchone())


def _seller(conn):
    return dict(conn.execute("SELECT * FROM sellers WHERE agent_pubkey = 'seller'").fetchone())


def _agent_balance(conn, pubkey):
    return conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (pubkey,)).fetchone()["cu_balance"]


# ── settle_trade ────────────────────────────────────────

def test_settle_trade_seller_receives_correct_amount():
    conn = _setup(price_cu=100.0)
    trade = _trade(conn)
    seller_receives, fee_cu = settle_trade(conn, trade)
    conn.commit()
    assert abs(seller_receives - 98.5) < 1e-9
    assert abs(fee_cu - 1.5) < 1e-9


def test_settle_trade_credits_seller_balance():
    conn = _setup(price_cu=100.0, cu_balance_seller=10.0)
    trade = _trade(conn)
    settle_trade(conn, trade)
    conn.commit()
    assert abs(_agent_balance(conn, "seller") - 108.5) < 1e-9


def test_settle_trade_releases_escrow():
    conn = _setup(price_cu=100.0)
    trade = _trade(conn)
    settle_trade(conn, trade)
    conn.commit()
    escrow = conn.execute("SELECT status FROM escrow WHERE trade_id = 'trade1'").fetchone()
    assert escrow["status"] == "released"


def test_settle_trade_sets_status_completed():
    conn = _setup(price_cu=100.0)
    trade = _trade(conn)
    settle_trade(conn, trade)
    conn.commit()
    assert conn.execute("SELECT status FROM trades WHERE id = 'trade1'").fetchone()["status"] == "completed"


def test_settle_trade_fee_uses_fee_total_constant():
    """Fee must equal price * FEE_TOTAL (no hardcoded values)."""
    conn = _setup(price_cu=200.0)
    trade = _trade(conn)
    _, fee_cu = settle_trade(conn, trade)
    assert abs(fee_cu - 200.0 * FEE_TOTAL) < 1e-9


def test_settle_trade_records_event():
    conn = _setup(price_cu=100.0)
    trade = _trade(conn)
    settle_trade(conn, trade)
    conn.commit()
    event = conn.execute(
        "SELECT event_data FROM events WHERE event_type = 'settlement_complete'"
    ).fetchone()
    assert event is not None
    data = json.loads(event["event_data"])
    assert data["trade_id"] == "trade1"
    assert "fee_platform" not in data  # phantom sub-fees must not appear
    assert "fee_makers" not in data
    assert "fee_verify" not in data


# ── slash_bond ──────────────────────────────────────────

def test_slash_bond_refunds_buyer():
    conn = _setup(price_cu=100.0, cu_staked=50.0, cu_balance_buyer=0.0)
    trade = _trade(conn)
    seller = _seller(conn)
    slash_bond(conn, trade, seller, "latency_exceeded")
    conn.commit()
    # Buyer gets: full trade price from escrow + slash compensation
    slash_cu = 50.0 * BOND_SLASH
    expected = 100.0 + slash_cu * SLASH_TO_BUYER
    assert abs(_agent_balance(conn, "buyer") - expected) < 1e-9


def test_slash_bond_buyer_gets_slash_compensation():
    conn = _setup(price_cu=100.0, cu_staked=50.0, cu_balance_buyer=0.0)
    trade = _trade(conn)
    seller = _seller(conn)
    slash_bond(conn, trade, seller, "latency_exceeded")
    conn.commit()
    # slash = 5% of 50 = 2.5 CU; to_buyer = 50% of 2.5 = 1.25 CU
    slash_amount = 50.0 * BOND_SLASH
    to_buyer_expected = slash_amount * SLASH_TO_BUYER
    assert abs(_agent_balance(conn, "buyer") - (100.0 + to_buyer_expected)) < 1e-9


def test_slash_bond_reduces_seller_stake():
    conn = _setup(price_cu=100.0, cu_staked=50.0)
    trade = _trade(conn)
    seller = _seller(conn)
    slash_bond(conn, trade, seller, "latency_exceeded")
    conn.commit()
    slash_amount = 50.0 * BOND_SLASH
    new_stake = conn.execute(
        "SELECT cu_staked FROM sellers WHERE agent_pubkey = 'seller'"
    ).fetchone()["cu_staked"]
    assert abs(new_stake - (50.0 - slash_amount)) < 1e-9


def test_slash_bond_sets_trade_status_violated():
    conn = _setup(price_cu=100.0, cu_staked=50.0)
    trade = _trade(conn)
    seller = _seller(conn)
    slash_bond(conn, trade, seller, "latency_exceeded")
    conn.commit()
    assert conn.execute("SELECT status FROM trades WHERE id = 'trade1'").fetchone()["status"] == "violated"


def test_slash_bond_refunds_escrow():
    conn = _setup(price_cu=100.0, cu_staked=50.0)
    trade = _trade(conn)
    seller = _seller(conn)
    slash_bond(conn, trade, seller, "latency_exceeded")
    conn.commit()
    escrow = conn.execute("SELECT status FROM escrow WHERE trade_id = 'trade1'").fetchone()
    assert escrow["status"] == "refunded"


def test_slash_bond_zero_stake_still_refunds():
    """Seller with zero stake: buyer still gets full trade price refund."""
    conn = _setup(price_cu=100.0, cu_staked=0.0, cu_balance_buyer=0.0)
    trade = _trade(conn)
    seller = _seller(conn)
    slash_bond(conn, trade, seller, "callback_failed")
    conn.commit()
    assert abs(_agent_balance(conn, "buyer") - 100.0) < 1e-9


# ── maybe_set_sla ───────────────────────────────────────

def test_maybe_set_sla_requires_sample_size():
    conn = _setup()
    maybe_set_sla(conn, "seller", "cap123")
    conn.commit()
    # Not enough trades yet — bound stays 0
    row = conn.execute("SELECT latency_bound_us FROM sellers WHERE agent_pubkey = 'seller'").fetchone()
    assert row["latency_bound_us"] == 0


def test_maybe_set_sla_sets_bound_after_sample():
    conn = _setup()
    now_ns = time.time_ns()
    # Insert SLA_SAMPLE_SIZE completed trades with known latencies (all 1000 us)
    for i in range(SLA_SAMPLE_SIZE):
        conn.execute(
            "INSERT INTO trades (id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, "
            "start_ns, end_ns, status, latency_us) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"sla_trade_{i}", "buyer", "seller", "cap123", 10.0,
             now_ns + i, now_ns + i + 1_000_000, "completed", 1000),
        )
    conn.commit()
    maybe_set_sla(conn, "seller", "cap123")
    conn.commit()
    row = conn.execute("SELECT latency_bound_us FROM sellers WHERE agent_pubkey = 'seller'").fetchone()
    assert row["latency_bound_us"] > 0


# ── check_sla_decoherence ───────────────────────────────

def test_check_sla_decoherence_resets_old_sla():
    conn = _setup()
    # Manually set a stale SLA (older than 30 days)
    stale_ns = time.time_ns() - 3_000_000_000_000_000  # 34+ days ago
    conn.execute(
        "UPDATE sellers SET latency_bound_us = 5000, sla_set_at_ns = ? WHERE agent_pubkey = 'seller'",
        (stale_ns,),
    )
    conn.commit()
    check_sla_decoherence(conn, "seller", "cap123")
    conn.commit()
    row = conn.execute("SELECT latency_bound_us FROM sellers WHERE agent_pubkey = 'seller'").fetchone()
    assert row["latency_bound_us"] == 0


def test_check_sla_decoherence_keeps_fresh_sla():
    conn = _setup()
    fresh_ns = time.time_ns() - 1_000_000_000  # 1 second ago
    conn.execute(
        "UPDATE sellers SET latency_bound_us = 5000, sla_set_at_ns = ? WHERE agent_pubkey = 'seller'",
        (fresh_ns,),
    )
    conn.commit()
    check_sla_decoherence(conn, "seller", "cap123")
    conn.commit()
    row = conn.execute("SELECT latency_bound_us FROM sellers WHERE agent_pubkey = 'seller'").fetchone()
    assert row["latency_bound_us"] == 5000
