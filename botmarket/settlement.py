# settlement.py — CU ledger (debit/credit/escrow/slash)
import json
from constants import FEE_TOTAL, FEE_PLATFORM, FEE_MAKERS, FEE_VERIFY, BOND_SLASH, SLASH_TO_BUYER
from events import record_event


def settle_trade(conn, trade):
    """Settle a passed trade: credit seller (price × 0.985), delete escrow."""
    price = trade["price_cu"]
    fee_cu = price * FEE_TOTAL
    seller_receives = price - fee_cu

    # Delete escrow
    conn.execute("DELETE FROM escrow WHERE trade_id = ?", (trade["id"],))
    # Credit seller
    conn.execute(
        "UPDATE agents SET cu_balance = cu_balance + ? WHERE pubkey = ?",
        (seller_receives, trade["seller_pubkey"]),
    )
    # Update trade status
    conn.execute(
        "UPDATE trades SET status = 'completed' WHERE id = ?", (trade["id"],)
    )
    # Record event
    record_event(conn, "settlement_complete", json.dumps({
        "trade_id": trade["id"],
        "buyer": trade["buyer_pubkey"],
        "seller": trade["seller_pubkey"],
        "seller_receives": seller_receives,
        "fee_cu": fee_cu,
        "fee_platform": price * FEE_PLATFORM,
        "fee_makers": price * FEE_MAKERS,
        "fee_verify": price * FEE_VERIFY,
    }))

    return seller_receives, fee_cu


def slash_bond(conn, trade, seller, reason):
    """Slash seller bond: refund buyer, slash 5% of staked CU."""
    # Refund buyer from escrow
    conn.execute(
        "UPDATE agents SET cu_balance = cu_balance + ? WHERE pubkey = ?",
        (trade["price_cu"], trade["buyer_pubkey"]),
    )
    conn.execute("DELETE FROM escrow WHERE trade_id = ?", (trade["id"],))

    # Slash seller bond
    slash_amount = seller["cu_staked"] * BOND_SLASH
    to_buyer = slash_amount * SLASH_TO_BUYER

    if slash_amount > 0:
        conn.execute(
            "UPDATE sellers SET cu_staked = cu_staked - ? WHERE agent_pubkey = ? AND capability_hash = ?",
            (slash_amount, trade["seller_pubkey"], trade["capability_hash"]),
        )
        conn.execute(
            "UPDATE agents SET cu_balance = cu_balance + ? WHERE pubkey = ?",
            (to_buyer, trade["buyer_pubkey"]),
        )

    # Update trade status
    conn.execute(
        "UPDATE trades SET status = 'violated' WHERE id = ?", (trade["id"],)
    )
    # Record event
    record_event(conn, "bond_slashed", json.dumps({
        "trade_id": trade["id"],
        "buyer": trade["buyer_pubkey"],
        "seller": trade["seller_pubkey"],
        "slash_amount": slash_amount,
        "to_buyer": to_buyer,
        "reason": reason,
    }))
