# matching.py — Match engine (seller tables + match logic)
import time
from collections import defaultdict
from constants import CIRCUIT_BREAKER_STRIKES

CIRCUIT_BREAKER_COOLDOWN_NS = 60_000_000_000  # 60 seconds — block matching after any failure

# In-memory seller tables: {capability_hash: [seller_dict, ...]}
# Always sorted by (price_cu ASC, latency_bound_us ASC)
_seller_tables = defaultdict(list)

# Circuit breaker: {(agent_pubkey, capability_hash): consecutive_failure_count}
_failure_counts = {}

# Cooldown: {(agent_pubkey, capability_hash): timestamp_ns of last failure}
_failure_timestamps = {}


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
    """Upsert a seller into the in-memory table, keeping sort order."""
    cap_hash = seller["capability_hash"]
    key = (seller["agent_pubkey"], cap_hash)
    # Replace any existing entry for the same (agent_pubkey, capability_hash)
    _seller_tables[cap_hash] = [
        s for s in _seller_tables[cap_hash]
        if s["agent_pubkey"] != seller["agent_pubkey"]
    ]
    _seller_tables[cap_hash].append(seller)
    _seller_tables[cap_hash].sort(key=lambda s: (s["price_cu"], s["latency_bound_us"]))
    # Clear circuit breaker state on re-registration (seller fixed their callback)
    _failure_counts.pop(key, None)
    _failure_timestamps.pop(key, None)


def get_sellers(capability_hash):
    """Return list of sellers for a capability hash (sorted)."""
    return _seller_tables.get(capability_hash, [])


def match_request(capability_hash, max_price_cu=None, max_latency_us=None, buyer_pubkey=None):
    """Find best seller: cheapest that passes all filters and has capacity."""
    sellers = _seller_tables.get(capability_hash, [])
    for seller in sellers:
        if buyer_pubkey is not None and seller["agent_pubkey"] == buyer_pubkey:
            continue
        if max_price_cu is not None and seller["price_cu"] > max_price_cu:
            continue
        if max_latency_us is not None and seller["latency_bound_us"] > max_latency_us:
            continue
        if seller["active_calls"] >= seller["capacity"]:
            continue
        key = (seller["agent_pubkey"], capability_hash)
        if _failure_counts.get(key, 0) >= CIRCUIT_BREAKER_STRIKES:
            continue
        # Cooldown: block matching for 60s after any failure to prevent rapid re-match race
        last_fail = _failure_timestamps.get(key)
        if last_fail is not None and (time.time_ns() - last_fail) < CIRCUIT_BREAKER_COOLDOWN_NS:
            continue
        return seller
    return None


def increment_active_calls(agent_pubkey, capability_hash):
    """Increment active_calls for a seller in-memory."""
    sellers = _seller_tables.get(capability_hash, [])
    for seller in sellers:
        if seller["agent_pubkey"] == agent_pubkey:
            seller["active_calls"] += 1
            break


def decrement_active_calls(agent_pubkey, capability_hash):
    """Decrement active_calls for a seller in-memory."""
    sellers = _seller_tables.get(capability_hash, [])
    for seller in sellers:
        if seller["agent_pubkey"] == agent_pubkey:
            seller["active_calls"] = max(0, seller["active_calls"] - 1)
            break


def remove_seller(agent_pubkey, capability_hash):
    """Remove a seller from the in-memory table."""
    sellers = _seller_tables.get(capability_hash, [])
    _seller_tables[capability_hash] = [
        s for s in sellers if s["agent_pubkey"] != agent_pubkey
    ]
    _failure_counts.pop((agent_pubkey, capability_hash), None)
    _failure_timestamps.pop((agent_pubkey, capability_hash), None)


def record_failure(agent_pubkey, capability_hash):
    """Record a callback failure. Returns True if seller was auto-suspended."""
    key = (agent_pubkey, capability_hash)
    _failure_counts[key] = _failure_counts.get(key, 0) + 1
    _failure_timestamps[key] = time.time_ns()
    return _failure_counts[key] >= CIRCUIT_BREAKER_STRIKES


def record_success(agent_pubkey, capability_hash):
    """Reset failure counter on successful callback."""
    key = (agent_pubkey, capability_hash)
    _failure_counts.pop(key, None)
    _failure_timestamps.pop(key, None)


def clear_tables():
    """Clear in-memory seller tables. Used by tests for isolation."""
    _seller_tables.clear()
    _failure_counts.clear()
    _failure_timestamps.clear()
