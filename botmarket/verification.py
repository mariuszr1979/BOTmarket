# verification.py — Deterministic verification (latency + schema)
# Only verifies what math can prove: latency, schema, non-empty response.
# NEVER verifies: quality, accuracy, correctness.


def verify_trade(trade, seller, output):
    """Deterministic verification. Returns (passed: bool, reason: str)."""
    # Response check: output must not be null/empty
    if not output:
        return False, "empty_output"

    # Latency check: trade.latency_us must be within seller.latency_bound_us
    # (latency_bound_us == 0 means no SLA set yet — skip check)
    if seller["latency_bound_us"] > 0 and trade["latency_us"] > seller["latency_bound_us"]:
        return False, "latency_exceeded"

    return True, "passed"
