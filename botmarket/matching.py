# matching.py — Match engine (seller tables + match logic)
from collections import defaultdict


# In-memory seller tables: {capability_hash: [seller_dict, ...]}
# Always sorted by (price_cu ASC, latency_bound_us ASC)
_seller_tables = defaultdict(list)


def rebuild_seller_tables(conn):
    """Rebuild in-memory seller tables from SQLite. Called on startup."""
    _seller_tables.clear()
    rows = conn.execute(
        "SELECT agent_pubkey, capability_hash, price_cu, latency_bound_us, "
        "capacity, active_calls, cu_staked, registered_at_ns FROM sellers"
    ).fetchall()
    for row in rows:
        seller = {
            "agent_pubkey": row["agent_pubkey"],
            "capability_hash": row["capability_hash"],
            "price_cu": row["price_cu"],
            "latency_bound_us": row["latency_bound_us"],
            "capacity": row["capacity"],
            "active_calls": row["active_calls"],
            "cu_staked": row["cu_staked"],
        }
        _seller_tables[row["capability_hash"]].append(seller)
    for sellers in _seller_tables.values():
        sellers.sort(key=lambda s: (s["price_cu"], s["latency_bound_us"]))


def add_seller(seller):
    """Add a seller to the in-memory table, keeping sort order."""
    cap_hash = seller["capability_hash"]
    _seller_tables[cap_hash].append(seller)
    _seller_tables[cap_hash].sort(key=lambda s: (s["price_cu"], s["latency_bound_us"]))


def get_sellers(capability_hash):
    """Return list of sellers for a capability hash (sorted)."""
    return _seller_tables.get(capability_hash, [])
