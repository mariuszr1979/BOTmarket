# test_events.py — Event log tests
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import init_db
from events import record_event


def test_record_event_inserts_row():
    conn = init_db(":memory:")
    record_event(conn, "test_event", json.dumps({"key": "val"}))
    conn.commit()
    row = conn.execute("SELECT event_type, event_data FROM events").fetchone()
    assert row["event_type"] == "test_event"
    assert json.loads(row["event_data"]) == {"key": "val"}
    conn.close()


def test_record_event_timestamp_is_ns():
    conn = init_db(":memory:")
    record_event(conn, "test_event", "{}")
    conn.commit()
    row = conn.execute("SELECT timestamp_ns FROM events").fetchone()
    # nanosecond timestamps are > 1e18
    assert row["timestamp_ns"] > 1_000_000_000_000_000_000
    conn.close()


def test_record_event_sequential_seq():
    conn = init_db(":memory:")
    record_event(conn, "first", "{}")
    record_event(conn, "second", "{}")
    conn.commit()
    rows = conn.execute("SELECT seq, event_type FROM events ORDER BY seq").fetchall()
    assert rows[0]["seq"] < rows[1]["seq"]
    assert rows[0]["event_type"] == "first"
    assert rows[1]["event_type"] == "second"
    conn.close()
