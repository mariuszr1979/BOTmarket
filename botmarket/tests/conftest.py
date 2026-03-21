"""
conftest.py — pytest fixtures shared across all tests.

pg_clean (autouse): when DATABASE_URL is set, TRUNCATE all PostgreSQL tables
and restart sequences before each test so tests are fully isolated.
In SQLite mode this fixture is a no-op.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

_ALL_TABLES = "escrow, trades, sellers, schemas, events, agents"


@pytest.fixture(autouse=True)
def pg_clean():
    """Truncate all PG tables before each test. No-op in SQLite mode."""
    import db as _db
    if not _db._is_pg():
        yield
        return

    pool = _db._get_pg_pool()
    conn = pool.getconn()
    try:
        conn.execute(f"TRUNCATE TABLE {_ALL_TABLES} RESTART IDENTITY CASCADE")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        pool.putconn(conn)

    yield
