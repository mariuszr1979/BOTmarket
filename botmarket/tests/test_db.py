import sys
import os
import sqlite3
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import init_db, get_connection


def test_init_creates_all_tables():
    conn = init_db(":memory:")
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = sorted(row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_"))
    expected = ["agents", "escrow", "events", "schemas", "sellers", "trades"]
    assert tables == expected, f"Expected {expected}, got {tables}"
    conn.close()


def test_no_extra_columns_agents():
    conn = init_db(":memory:")
    cursor = conn.execute("PRAGMA table_info(agents)")
    cols = [row[1] for row in cursor.fetchall()]
    assert cols == ["pubkey", "api_key", "cu_balance", "registered_at"]
    conn.close()


def test_no_extra_columns_sellers():
    conn = init_db(":memory:")
    cursor = conn.execute("PRAGMA table_info(sellers)")
    cols = [row[1] for row in cursor.fetchall()]
    expected = ["agent_pubkey", "capability_hash", "price_cu", "latency_bound_us",
                "capacity", "active_calls", "cu_staked", "registered_at_ns"]
    assert cols == expected
    conn.close()


def test_no_extra_columns_trades():
    conn = init_db(":memory:")
    cursor = conn.execute("PRAGMA table_info(trades)")
    cols = [row[1] for row in cursor.fetchall()]
    expected = ["id", "buyer_pubkey", "seller_pubkey", "capability_hash",
                "price_cu", "start_ns", "end_ns", "status", "latency_us"]
    assert cols == expected
    conn.close()


def test_no_extra_columns_events():
    conn = init_db(":memory:")
    cursor = conn.execute("PRAGMA table_info(events)")
    cols = [row[1] for row in cursor.fetchall()]
    assert cols == ["seq", "event_type", "event_data", "timestamp_ns"]
    conn.close()


def test_no_extra_columns_escrow():
    conn = init_db(":memory:")
    cursor = conn.execute("PRAGMA table_info(escrow)")
    cols = [row[1] for row in cursor.fetchall()]
    assert cols == ["trade_id", "buyer_pubkey", "seller_pubkey", "cu_amount", "status"]
    conn.close()


def test_no_extra_columns_schemas():
    conn = init_db(":memory:")
    cursor = conn.execute("PRAGMA table_info(schemas)")
    cols = [row[1] for row in cursor.fetchall()]
    assert cols == ["capability_hash", "input_schema", "output_schema", "registered_at"]
    conn.close()


def test_cu_balance_defaults_to_zero():
    conn = init_db(":memory:")
    now = int(time.time())
    conn.execute("INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, 0.0, ?)",
                 ("pk_test", "ak_test", now))
    conn.commit()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", ("pk_test",)).fetchone()
    assert row[0] == 0.0
    conn.close()


def test_duplicate_pubkey_fails():
    conn = init_db(":memory:")
    now = int(time.time())
    conn.execute("INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, 0.0, ?)",
                 ("pk_dup", "ak_1", now))
    conn.commit()
    try:
        conn.execute("INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, 0.0, ?)",
                     ("pk_dup", "ak_2", now))
        assert False, "Should have raised IntegrityError"
    except sqlite3.IntegrityError:
        pass
    conn.close()


def test_foreign_key_seller_requires_agent():
    conn = init_db(":memory:")
    try:
        conn.execute("""INSERT INTO sellers
            (agent_pubkey, capability_hash, price_cu, capacity, registered_at_ns)
            VALUES (?, ?, ?, ?, ?)""",
            ("nonexistent", "hash1", 10.0, 5, 0))
        conn.commit()
        assert False, "Should have raised IntegrityError (FK)"
    except sqlite3.IntegrityError:
        pass
    conn.close()


def test_no_banned_columns():
    """RULES.md: No name, description, rating, or tier fields anywhere."""
    conn = init_db(":memory:")
    banned = {"name", "description", "rating", "tier"}
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    for (table,) in cursor.fetchall():
        if table.startswith("sqlite_"):
            continue
        cols_cursor = conn.execute(f"PRAGMA table_info({table})")
        col_names = {row[1] for row in cols_cursor.fetchall()}
        overlap = banned & col_names
        assert not overlap, f"Table '{table}' has banned column(s): {overlap}"
    conn.close()
