import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from constants import (
    FEE_TOTAL, FEE_PLATFORM, FEE_MAKERS, FEE_VERIFY,
    BOND_SLASH, SLASH_TO_BUYER, SLASH_TO_FUND,
)


def test_fee_components_sum_to_total():
    assert abs(FEE_PLATFORM + FEE_MAKERS + FEE_VERIFY - FEE_TOTAL) < 1e-10


def test_fee_total_is_1_5_percent():
    assert FEE_TOTAL == 0.015


def test_bond_slash_is_5_percent():
    assert BOND_SLASH == 0.05


def test_slash_distribution_sums_to_one():
    assert abs(SLASH_TO_BUYER + SLASH_TO_FUND - 1.0) < 1e-10


def test_200_cu_trade_math():
    """Pen-and-paper proof from MVP-PLAN.md."""
    price = 200.0
    fee = price * FEE_TOTAL
    seller_receives = price - fee
    platform = price * FEE_PLATFORM
    makers = price * FEE_MAKERS
    verify = price * FEE_VERIFY
    assert abs(fee - 3.0) < 1e-10
    assert abs(seller_receives - 197.0) < 1e-10
    assert abs(platform - 2.0) < 1e-10
    assert abs(makers - 0.6) < 1e-10
    assert abs(verify - 0.4) < 1e-10
    assert abs(seller_receives + platform + makers + verify - price) < 1e-10
