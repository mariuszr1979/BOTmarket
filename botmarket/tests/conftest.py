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

_ALL_TABLES = "faucet_state, escrow, trades, sellers, schemas, events, agents"


def _truncate_pg():
    """Truncate all PG tables and restart sequences."""
    import db as _db
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


def _clear_in_memory_caches():
    """Clear all module-level in-memory caches used by matching engine."""
    import matching
    matching.clear_tables()


@pytest.fixture(autouse=True)
def pg_clean():
    """Truncate all PG tables and clear caches before each test. No-op in SQLite mode."""
    import db as _db
    if not _db._is_pg():
        yield
        return

    _truncate_pg()
    _clear_in_memory_caches()

    yield

    # Post-test cleanup: truncate again to prevent leakage into the next test
    # if a test fails mid-way and leaves partial state.
    _truncate_pg()
    _clear_in_memory_caches()


@pytest.fixture
def db_setup(tmp_path, monkeypatch):
    """Set up the database for a test — PG-aware.

    In SQLite mode: creates a fresh DB in tmp_path.
    In PG mode: no-op (pg_clean handles isolation).
    """
    import db as _db
    import matching

    if _db._is_pg():
        # PG mode — schema already exists, pg_clean handles truncation.
        # Just ensure init_db() was called (idempotent).
        conn = _db.init_db()
        conn.close()
    else:
        # SQLite mode — fresh file-based DB per test.
        db_path = str(tmp_path / "test.db")
        monkeypatch.setenv("BOTMARKET_DB", db_path)
        monkeypatch.setattr(_db, "DB_PATH", db_path)
        _db.init_db(db_path).close()

    matching.clear_tables()
    return None
    _clear_in_memory_caches()
