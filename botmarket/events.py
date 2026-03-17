# events.py — Event log (record + query raw facts)
import time


def record_event(conn, event_type, event_data):
    conn.execute(
        "INSERT INTO events (event_type, event_data, timestamp_ns) VALUES (?, ?, ?)",
        (event_type, event_data, time.time_ns()),
    )
