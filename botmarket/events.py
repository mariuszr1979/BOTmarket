# events.py — Event log (record + query raw facts)
import time


def record_event(conn, event_type, event_data):
    conn.execute(
        "INSERT INTO events (event_type, event_data, timestamp_ns) VALUES (?, ?, ?)",
        (event_type, event_data, time.time_ns()),
    )


def query_events(conn, agent_pubkey, event_type=None, limit=100):
    """Query events where agent_pubkey appears in event_data JSON."""
    sql = "SELECT seq, event_type, event_data, timestamp_ns FROM events WHERE event_data LIKE ?"
    params = [f"%{agent_pubkey}%"]
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    sql += " ORDER BY seq ASC LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(sql, params).fetchall()]
