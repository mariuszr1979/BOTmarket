import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from constants import (
    FEE_TOTAL,
    BOND_SLASH, SLASH_TO_BUYER, SLASH_BURN,
)


def test_fee_total_is_1_5_percent():
    assert FEE_TOTAL == 0.015


def test_bond_slash_is_5_percent():
    assert BOND_SLASH == 0.05


def test_slash_distribution_sums_to_one():
    """50% to buyer + 50% burn = 100% of slashed amount accounted for."""
    assert abs(SLASH_TO_BUYER + SLASH_BURN - 1.0) < 1e-10


def test_100_cu_trade_math():
    """Settlement math: buyer pays 100 CU, seller receives 98.5, 1.5 burned as fee."""
    price = 100.0
    fee = price * FEE_TOTAL
    seller_receives = price - fee
    assert abs(fee - 1.5) < 1e-10
    assert abs(seller_receives - 98.5) < 1e-10
    assert abs(seller_receives + fee - price) < 1e-10


def test_slash_math():
    """Slash math: 5% of stake slashed; 50% to buyer, 50% burned."""
    stake = 100.0
    slash_amount = stake * BOND_SLASH
    to_buyer = slash_amount * SLASH_TO_BUYER
    burned = slash_amount * SLASH_BURN
    assert abs(slash_amount - 5.0) < 1e-10
    assert abs(to_buyer - 2.5) < 1e-10
    assert abs(burned - 2.5) < 1e-10
    assert abs(to_buyer + burned - slash_amount) < 1e-10
