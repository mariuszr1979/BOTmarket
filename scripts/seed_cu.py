#!/usr/bin/env python3
"""
seed_cu.py — Credit free CU to a beta participant.

Usage:
    python scripts/seed_cu.py <pubkey> [amount_cu]

Examples:
    python scripts/seed_cu.py abc123def456 1000000
    python scripts/seed_cu.py abc123def456          # uses BETA_SEED_CU env or 1_000_000

The script:
  - Creates the agent row if it doesn't exist yet
  - Credits the specified CU amount to the agent's balance
  - Is idempotent on re-run with the same pubkey (credits again each time — intentional)
  - Works against both SQLite (dev) and PostgreSQL (prod) via DATABASE_URL env var

Environment:
    DATABASE_URL    postgresql://... (optional; defaults to SQLite botmarket.db)
    BOTMARKET_DB    path to SQLite file (optional; default botmarket.db)
    BETA_SEED_CU    default grant amount when no amount given on CLI
"""

import json
import os
import sys
import time

# Allow running from the project root or from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "botmarket"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import get_connection, init_db  # noqa: E402  (path manipulation above)
from events import record_event  # noqa: E402


DEFAULT_GRANT = int(os.environ.get("BETA_SEED_CU", 1_000_000))


def seed(pubkey: str, amount_cu: float) -> float:
    if amount_cu <= 0:
        raise ValueError(f"amount_cu must be positive, got {amount_cu}")

    conn = get_connection()
    try:
        now_ns = time.time_ns()
        # Upsert: create agent if missing, add CU either way
        conn.execute(
            """
            INSERT INTO agents (pubkey, api_key, cu_balance, registered_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (pubkey) DO UPDATE SET cu_balance = cu_balance + excluded.cu_balance
            """,
            (pubkey, None, amount_cu, now_ns),
        )
        record_event(conn, "cu_seeded", json.dumps({"agent": pubkey, "amount_cu": amount_cu}))
        row = conn.execute(
            "SELECT cu_balance FROM agents WHERE pubkey = ?", (pubkey,)
        ).fetchone()
        if hasattr(conn, "commit"):
            conn.commit()
        return row["cu_balance"] if row else amount_cu
    finally:
        conn.close()


def _pg_seed(pubkey: str, amount_cu: float) -> float:
    """PostgreSQL path — uses the pool via get_connection()."""
    import db as _db
    conn = _db.get_connection()
    try:
        now_ns = time.time_ns()
        conn.execute(
            """
            INSERT INTO agents (pubkey, api_key, cu_balance, registered_at)
            VALUES (%s, NULL, %s, %s)
            ON CONFLICT (pubkey) DO UPDATE SET cu_balance = agents.cu_balance + %s
            """,
            (pubkey, amount_cu, now_ns, amount_cu),
        )
        record_event(conn, "cu_seeded", json.dumps({"agent": pubkey, "amount_cu": amount_cu}))
        row = conn.execute(
            "SELECT cu_balance FROM agents WHERE pubkey = %s", (pubkey,)
        ).fetchone()
        conn.commit()
        return float(row["cu_balance"])
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pubkey = sys.argv[1].strip()
    if not pubkey:
        print("ERROR: pubkey cannot be empty", file=sys.stderr)
        sys.exit(1)

    try:
        amount_cu = float(sys.argv[2]) if len(sys.argv) >= 3 else float(DEFAULT_GRANT)
    except ValueError:
        print(f"ERROR: invalid amount '{sys.argv[2]}'", file=sys.stderr)
        sys.exit(1)

    if amount_cu <= 0:
        print("ERROR: amount must be positive", file=sys.stderr)
        sys.exit(1)

    # Ensure schema exists (no-op if already initialised)
    init_db().close()

    import db as _db
    if _db._is_pg():
        balance = _pg_seed(pubkey, amount_cu)
    else:
        balance = seed(pubkey, amount_cu)

    print(f"OK  pubkey={pubkey[:16]}...  credited={amount_cu:,.0f} CU  balance={balance:,.0f} CU")


if __name__ == "__main__":
    main()
