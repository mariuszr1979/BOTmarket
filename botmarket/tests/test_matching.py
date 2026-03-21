# test_matching.py — Match engine tests
# Implemented in Step 5
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from matching import add_seller, get_sellers, match_request, _seller_tables


@pytest.fixture(autouse=True)
def clear_sellers():
    """Reset in-memory seller tables before each test."""
    _seller_tables.clear()
    yield
    _seller_tables.clear()


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
