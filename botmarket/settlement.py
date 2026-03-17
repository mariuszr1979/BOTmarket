# settlement.py — CU ledger (debit/credit/escrow/slash)
import json
from constants import FEE_TOTAL, FEE_PLATFORM, FEE_MAKERS, FEE_VERIFY, BOND_SLASH, SLASH_TO_BUYER, SLA_SAMPLE_SIZE, SLA_MARGIN
from events import record_event


def maybe_set_sla(conn, seller_pubkey, capability_hash):
    """After SLA_SAMPLE_SIZE completed trades, lock latency_bound_us = p99 + 20%."""
    row = conn.execute(
        "SELECT latency_bound_us FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
        (seller_pubkey, capability_hash),
    ).fetchone()
    if row is None or row["latency_bound_us"] > 0:
        return  # already set or seller gone

    rows = conn.execute(
        "SELECT latency_us FROM trades WHERE seller_pubkey = ? AND capability_hash = ? "
        "AND status = 'completed' AND latency_us IS NOT NULL ORDER BY rowid ASC LIMIT ?",
        (seller_pubkey, capability_hash, SLA_SAMPLE_SIZE),
    ).fetchall()
    if len(rows) < SLA_SAMPLE_SIZE:
        return

    latencies = sorted(r["latency_us"] for r in rows)
    p99_idx = int(SLA_SAMPLE_SIZE * 0.99) - 1  # 0-based index for 50th sample → idx 49
    p99 = latencies[min(p99_idx, len(latencies) - 1)]
    bound = int(p99 * (1 + SLA_MARGIN))

    conn.execute(
        "UPDATE sellers SET latency_bound_us = ? WHERE agent_pubkey = ? AND capability_hash = ?",
        (bound, seller_pubkey, capability_hash),
    )
    record_event(conn, "sla_set", json.dumps({
        "seller": seller_pubkey,
        "capability_hash": capability_hash,
        "p99_us": p99,
        "latency_bound_us": bound,
        "sample_size": SLA_SAMPLE_SIZE,
    }))


def settle_trade(conn, trade):
    """Settle a passed trade: credit seller (price × 0.985), release escrow."""
    price = trade["price_cu"]
    fee_cu = price * FEE_TOTAL
    seller_receives = price - fee_cu

    # Release escrow
    conn.execute("UPDATE escrow SET status = 'released' WHERE trade_id = ?", (trade["id"],))
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
    conn.execute("UPDATE escrow SET status = 'refunded' WHERE trade_id = ?", (trade["id"],))

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
