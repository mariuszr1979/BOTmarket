# test_matching.py — Match engine tests
# Implemented in Step 5
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from matching import add_seller, get_sellers, match_request, _seller_tables, record_failure, record_success, remove_seller, _failure_counts, _failure_timestamps, CIRCUIT_BREAKER_COOLDOWN_NS
from constants import CIRCUIT_BREAKER_STRIKES


@pytest.fixture(autouse=True)
def clear_sellers():
    """Reset in-memory seller tables before each test."""
    _seller_tables.clear()
    _failure_counts.clear()
    _failure_timestamps.clear()
    yield
    _seller_tables.clear()
    _failure_counts.clear()
    _failure_timestamps.clear()


def _make_seller(agent_pubkey, cap_hash="abc123", price_cu=5.0, capacity=3, active_calls=0):
    return {
        "agent_pubkey": agent_pubkey,
        "capability_hash": cap_hash,
        "price_cu": price_cu,
        "latency_bound_us": 0,
        "capacity": capacity,
        "active_calls": active_calls,
        "cu_staked": price_cu,
    }


def test_add_seller_appears_in_list():
    seller = _make_seller("agent-A")
    add_seller(seller)
    sellers = get_sellers("abc123")
    assert len(sellers) == 1
    assert sellers[0]["agent_pubkey"] == "agent-A"


def test_add_seller_upsert_replaces_existing():
    """Re-registering the same agent+capability should NOT duplicate the entry."""
    add_seller(_make_seller("agent-A", price_cu=5.0))
    add_seller(_make_seller("agent-A", price_cu=3.0))  # re-register with lower price

    sellers = get_sellers("abc123")
    assert len(sellers) == 1, "re-registration must not create a duplicate"
    assert sellers[0]["price_cu"] == 3.0, "updated price should replace old price"


def test_add_two_distinct_sellers_both_present():
    add_seller(_make_seller("agent-A", price_cu=5.0))
    add_seller(_make_seller("agent-B", price_cu=4.0))

    sellers = get_sellers("abc123")
    assert len(sellers) == 2
    # Cheaper seller comes first
    assert sellers[0]["agent_pubkey"] == "agent-B"
    assert sellers[1]["agent_pubkey"] == "agent-A"


def test_match_picks_cheapest_seller():
    add_seller(_make_seller("expensive", price_cu=10.0))
    add_seller(_make_seller("cheap", price_cu=3.0))

    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "cheap"


def test_match_respects_max_price():
    add_seller(_make_seller("agent-A", price_cu=8.0))
    result = match_request("abc123", max_price_cu=5.0)
    assert result is None


def test_match_skips_full_capacity():
    add_seller(_make_seller("full", price_cu=3.0, capacity=2, active_calls=2))
    add_seller(_make_seller("available", price_cu=5.0, capacity=2, active_calls=0))
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "available"


# ── Circuit breaker tests ──────────────────────────────────────────

def test_record_failure_returns_false_below_threshold():
    add_seller(_make_seller("agent-A"))
    for _ in range(CIRCUIT_BREAKER_STRIKES - 1):
        assert record_failure("agent-A", "abc123") is False


def test_record_failure_returns_true_at_threshold():
    add_seller(_make_seller("agent-A"))
    for _ in range(CIRCUIT_BREAKER_STRIKES - 1):
        record_failure("agent-A", "abc123")
    assert record_failure("agent-A", "abc123") is True


def test_match_skips_circuit_broken_seller():
    add_seller(_make_seller("broken", price_cu=1.0))
    add_seller(_make_seller("healthy", price_cu=5.0))
    for _ in range(CIRCUIT_BREAKER_STRIKES):
        record_failure("broken", "abc123")
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "healthy"


def test_match_returns_none_when_all_circuit_broken():
    add_seller(_make_seller("broken", price_cu=1.0))
    for _ in range(CIRCUIT_BREAKER_STRIKES):
        record_failure("broken", "abc123")
    result = match_request("abc123", max_price_cu=20)
    assert result is None


def test_record_success_resets_failure_count():
    add_seller(_make_seller("agent-A", price_cu=1.0))
    for _ in range(CIRCUIT_BREAKER_STRIKES - 1):
        record_failure("agent-A", "abc123")
    record_success("agent-A", "abc123")
    # Should be matchable again
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "agent-A"


def test_remove_seller_clears_from_table_and_failures():
    add_seller(_make_seller("agent-A"))
    record_failure("agent-A", "abc123")
    remove_seller("agent-A", "abc123")
    assert get_sellers("abc123") == []
    assert ("agent-A", "abc123") not in _failure_counts
    assert ("agent-A", "abc123") not in _failure_timestamps


# ── Cooldown tests ─────────────────────────────────────────────────


def test_cooldown_blocks_match_after_single_failure():
    """After one failure, seller is blocked for CIRCUIT_BREAKER_COOLDOWN_NS."""
    add_seller(_make_seller("flaky", price_cu=1.0))
    add_seller(_make_seller("healthy", price_cu=5.0))
    record_failure("flaky", "abc123")
    # Immediately after failure, flaky should be skipped (in cooldown)
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "healthy"


def test_cooldown_expires_after_duration():
    """After cooldown period, seller is matchable again (if below strike threshold)."""
    import time as _time
    add_seller(_make_seller("flaky", price_cu=1.0))
    record_failure("flaky", "abc123")
    # Manually backdate the failure timestamp so cooldown has expired
    key = ("flaky", "abc123")
    _failure_timestamps[key] = _time.time_ns() - CIRCUIT_BREAKER_COOLDOWN_NS - 1
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "flaky"


def test_re_registration_clears_failure_state():
    """Re-registering a seller should clear circuit breaker and cooldown state."""
    add_seller(_make_seller("agent-A", price_cu=3.0))
    record_failure("agent-A", "abc123")
    record_failure("agent-A", "abc123")
    key = ("agent-A", "abc123")
    assert _failure_counts.get(key, 0) == 2
    assert key in _failure_timestamps
    # Re-register = seller fixed their callback
    add_seller(_make_seller("agent-A", price_cu=3.0))
    assert _failure_counts.get(key, 0) == 0 or key not in _failure_counts
    assert key not in _failure_timestamps
    # Should be matchable immediately
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "agent-A"


def test_record_success_clears_cooldown():
    """A successful trade should clear cooldown timestamp."""
    add_seller(_make_seller("agent-A", price_cu=1.0))
    record_failure("agent-A", "abc123")
    key = ("agent-A", "abc123")
    assert key in _failure_timestamps
    record_success("agent-A", "abc123")
    assert key not in _failure_timestamps
    # Should be matchable immediately
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "agent-A"


# ── Self-trade prevention tests ────────────────────────────────────


def test_match_skips_self_trade():
    """buyer_pubkey == seller agent_pubkey should never match."""
    add_seller(_make_seller("agent-A", price_cu=1.0))
    result = match_request("abc123", max_price_cu=20, buyer_pubkey="agent-A")
    assert result is None


def test_match_self_trade_falls_through_to_next_seller():
    """If cheapest seller is the buyer, skip to next."""
    add_seller(_make_seller("agent-A", price_cu=1.0))
    add_seller(_make_seller("agent-B", price_cu=5.0))
    result = match_request("abc123", max_price_cu=20, buyer_pubkey="agent-A")
    assert result is not None
    assert result["agent_pubkey"] == "agent-B"


def test_match_without_buyer_pubkey_still_works():
    """Backward compatibility: buyer_pubkey=None doesn't filter."""
    add_seller(_make_seller("agent-A", price_cu=1.0))
    result = match_request("abc123", max_price_cu=20)
    assert result["agent_pubkey"] == "agent-A"
