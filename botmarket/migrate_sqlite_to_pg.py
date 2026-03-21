#!/usr/bin/env python3
"""One-time migration: SQLite → PostgreSQL.

Usage:
    DATABASE_URL=postgresql://botmarket:botmarket@localhost:5432/botmarket \
    python migrate_sqlite_to_pg.py [sqlite_db_path]

Defaults to BOTMARKET_DB env var or 'botmarket.db' if no path given.
"""
import os
import sqlite3
import sys


TABLES = ["agents", "schemas", "sellers", "trades", "events", "escrow"]


def main():
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BOTMARKET_DB", "botmarket.db")
    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    import psycopg
    from psycopg.rows import dict_row

    # Connect SQLite (read-only)
    sq = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    sq.row_factory = sqlite3.Row

    # Ensure sla_set_at_ns column exists in SQLite (old DBs may lack it)
    sq_seller_cols = [row[1] for row in sq.execute("PRAGMA table_info(sellers)").fetchall()]
    if "sla_set_at_ns" not in sq_seller_cols:
        # Re-open read-write to add the column
        sq.close()
        sq = sqlite3.connect(sqlite_path)
        sq.row_factory = sqlite3.Row
        sq.execute("ALTER TABLE sellers ADD COLUMN sla_set_at_ns INTEGER")
        sq.commit()

    # Connect PostgreSQL
    pg = psycopg.connect(pg_url, row_factory=dict_row)

    # Initialize PG schema
    from db import SCHEMA_SQL_PG
    for stmt in SCHEMA_SQL_PG.split(';'):
        stmt = stmt.strip()
        if stmt:
            pg.execute(stmt)
    pg.commit()

    report = {}
    for table in TABLES:
        rows = sq.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            report[table] = 0
            continue

        cols = rows[0].keys()
        placeholders = ', '.join(['%s'] * len(cols))
        col_str = ', '.join(cols)
        insert_sql = f"INSERT INTO {table} ({col_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        for row in rows:
            pg.execute(insert_sql, tuple(row[c] for c in cols))

        report[table] = len(rows)

    # Reset events sequence to match migrated data
    max_seq_row = sq.execute("SELECT MAX(seq) FROM events").fetchone()
    max_seq = max_seq_row[0] if max_seq_row else None
    if max_seq:
        pg.execute("SELECT setval('events_seq_seq', %s)", (max_seq,))

    pg.commit()

    # ── Verify ────────────────────────────────────────────
    print("\n=== Migration Report ===")
    all_ok = True
    for table in TABLES:
        pg_count = pg.execute(f"SELECT COUNT(*) as c FROM {table}").fetchone()["c"]
        sq_count = report[table]
        ok = "✓" if pg_count >= sq_count else "✗"
        if pg_count < sq_count:
            all_ok = False
        print(f"  {table}: {sq_count} → {pg_count} {ok}")

    # CU invariant
    sq_balances = sq.execute("SELECT COALESCE(SUM(cu_balance), 0) FROM agents").fetchone()[0]
    sq_escrow = sq.execute("SELECT COALESCE(SUM(cu_amount), 0) FROM escrow WHERE status = 'held'").fetchone()[0]
    sq_staked = sq.execute("SELECT COALESCE(SUM(cu_staked), 0) FROM sellers").fetchone()[0]
    sq_total = sq_balances + sq_escrow + sq_staked

    pg_balances = pg.execute("SELECT COALESCE(SUM(cu_balance), 0) as s FROM agents").fetchone()["s"]
    pg_escrow = pg.execute("SELECT COALESCE(SUM(cu_amount), 0) as s FROM escrow WHERE status = 'held'").fetchone()["s"]
    pg_staked = pg.execute("SELECT COALESCE(SUM(cu_staked), 0) as s FROM sellers").fetchone()["s"]
    pg_total = pg_balances + pg_escrow + pg_staked

    print(f"\n  CU Invariant:")
    print(f"    SQLite:     {sq_total:.4f} (balances={sq_balances:.4f} + escrow={sq_escrow:.4f} + staked={sq_staked:.4f})")
    print(f"    PostgreSQL: {pg_total:.4f} (balances={pg_balances:.4f} + escrow={pg_escrow:.4f} + staked={pg_staked:.4f})")
    diff = abs(sq_total - pg_total)
    ok = "✓" if diff < 0.001 else "✗"
    print(f"    Difference: {diff:.6f} {ok}")

    if not all_ok or diff >= 0.001:
        print("\n  ⚠ MIGRATION FAILED — verify manually")
        sq.close()
        pg.close()
        sys.exit(1)

    print("\n  ✓ Migration successful")
    sq.close()
    pg.close()


if __name__ == "__main__":
    main()
