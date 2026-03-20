import os
import re
import sqlite3

DB_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = os.environ.get("BOTMARKET_DB", "botmarket.db")

_pool = None  # PostgreSQL connection pool (lazy)


def _is_pg():
    return DB_URL.startswith("postgresql://")


# ── SQLite schema ─────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agents (
    pubkey        TEXT PRIMARY KEY,
    api_key       TEXT UNIQUE,
    cu_balance    REAL NOT NULL DEFAULT 0.0,
    registered_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS schemas (
    capability_hash TEXT PRIMARY KEY,
    input_schema    TEXT NOT NULL,
    output_schema   TEXT NOT NULL,
    registered_at   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sellers (
    agent_pubkey     TEXT NOT NULL REFERENCES agents(pubkey),
    capability_hash  TEXT NOT NULL REFERENCES schemas(capability_hash),
    price_cu         REAL NOT NULL,
    latency_bound_us INTEGER NOT NULL DEFAULT 0,
    capacity         INTEGER NOT NULL,
    active_calls     INTEGER NOT NULL DEFAULT 0,
    cu_staked        REAL NOT NULL DEFAULT 0.0,
    callback_url     TEXT,
    sla_set_at_ns    INTEGER,
    registered_at_ns INTEGER NOT NULL,
    PRIMARY KEY (agent_pubkey, capability_hash)
);

CREATE TABLE IF NOT EXISTS trades (
    id              TEXT PRIMARY KEY,
    buyer_pubkey    TEXT NOT NULL REFERENCES agents(pubkey),
    seller_pubkey   TEXT NOT NULL REFERENCES agents(pubkey),
    capability_hash TEXT NOT NULL,
    price_cu        REAL NOT NULL,
    start_ns        INTEGER,
    end_ns          INTEGER,
    status          TEXT NOT NULL DEFAULT 'matched',
    latency_us      INTEGER
);

CREATE TABLE IF NOT EXISTS events (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    previous_hash  TEXT NOT NULL DEFAULT '',
    event_hash     TEXT NOT NULL DEFAULT '',
    event_type     TEXT NOT NULL,
    event_data     TEXT NOT NULL,
    timestamp_ns   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS escrow (
    trade_id      TEXT PRIMARY KEY REFERENCES trades(id),
    buyer_pubkey  TEXT NOT NULL,
    seller_pubkey TEXT NOT NULL,
    cu_amount     REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'held'
);

CREATE TABLE IF NOT EXISTS faucet_state (
    agent_pubkey      TEXT PRIMARY KEY REFERENCES agents(pubkey),
    total_credited_cu REAL NOT NULL DEFAULT 0.0,
    last_drip_ns      INTEGER
);
"""


# ── PostgreSQL schema ─────────────────────────────────────

SCHEMA_SQL_PG = """
CREATE TABLE IF NOT EXISTS agents (
    pubkey        TEXT PRIMARY KEY,
    api_key       TEXT UNIQUE,
    cu_balance    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    registered_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS schemas (
    capability_hash TEXT PRIMARY KEY,
    input_schema    TEXT NOT NULL,
    output_schema   TEXT NOT NULL,
    registered_at   BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS sellers (
    agent_pubkey     TEXT NOT NULL REFERENCES agents(pubkey),
    capability_hash  TEXT NOT NULL REFERENCES schemas(capability_hash),
    price_cu         DOUBLE PRECISION NOT NULL,
    latency_bound_us BIGINT NOT NULL DEFAULT 0,
    capacity         INTEGER NOT NULL,
    active_calls     INTEGER NOT NULL DEFAULT 0,
    cu_staked        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    callback_url     TEXT,
    sla_set_at_ns    BIGINT,
    registered_at_ns BIGINT NOT NULL,
    PRIMARY KEY (agent_pubkey, capability_hash)
);

CREATE TABLE IF NOT EXISTS trades (
    id              TEXT PRIMARY KEY,
    buyer_pubkey    TEXT NOT NULL REFERENCES agents(pubkey),
    seller_pubkey   TEXT NOT NULL REFERENCES agents(pubkey),
    capability_hash TEXT NOT NULL,
    price_cu        DOUBLE PRECISION NOT NULL,
    start_ns        BIGINT,
    end_ns          BIGINT,
    status          TEXT NOT NULL DEFAULT 'matched',
    latency_us      BIGINT
);

CREATE TABLE IF NOT EXISTS events (
    seq           BIGSERIAL PRIMARY KEY,
    previous_hash TEXT NOT NULL DEFAULT '',
    event_hash    TEXT NOT NULL DEFAULT '',
    event_type    TEXT NOT NULL,
    event_data    TEXT NOT NULL,
    timestamp_ns  BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS escrow (
    trade_id      TEXT PRIMARY KEY REFERENCES trades(id),
    buyer_pubkey  TEXT NOT NULL,
    seller_pubkey TEXT NOT NULL,
    cu_amount     DOUBLE PRECISION NOT NULL,
    status        TEXT NOT NULL DEFAULT 'held'
);

CREATE TABLE IF NOT EXISTS faucet_state (
    agent_pubkey      TEXT PRIMARY KEY REFERENCES agents(pubkey),
    total_credited_cu DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_drip_ns      BIGINT
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp_ns);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_buyer ON trades(buyer_pubkey);
CREATE INDEX IF NOT EXISTS idx_trades_seller ON trades(seller_pubkey);
CREATE INDEX IF NOT EXISTS idx_sellers_capability ON sellers(capability_hash);
"""


# ── SQL translation (SQLite → PostgreSQL) ─────────────────

_PK_MAP = {
    'sellers': ('agent_pubkey', 'capability_hash'),
    'agents': ('pubkey',),
    'schemas': ('capability_hash',),
    'trades': ('id',),
    'escrow': ('trade_id',),
}


def _translate_sql(sql):
    """Translate SQLite-flavored SQL to PostgreSQL-compatible SQL."""
    sql = sql.replace('?', '%s')
    sql = re.sub(r'\bMAX\(\s*0\s*,', 'GREATEST(0,', sql)

    if re.search(r'INSERT\s+OR\s+IGNORE', sql, re.IGNORECASE):
        sql = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql, flags=re.IGNORECASE)
        return sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'

    m = re.search(r'INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)', sql, re.IGNORECASE)
    if m:
        table = m.group(1).lower()
        cols = [c.strip() for c in m.group(2).split(',')]
        pk_cols = _PK_MAP.get(table, ())
        update_cols = [c for c in cols if c not in pk_cols]
        sql = re.sub(r'INSERT\s+OR\s+REPLACE\s+INTO', 'INSERT INTO', sql, flags=re.IGNORECASE)
        conflict = ', '.join(pk_cols)
        updates = ', '.join(f'{c} = EXCLUDED.{c}' for c in update_cols)
        return sql.rstrip().rstrip(';') + f' ON CONFLICT ({conflict}) DO UPDATE SET {updates}'

    return sql


# ── PostgreSQL row type ─────────────────────────────────

class _HybridRow(dict):
    """Row supporting both dict[name] and row[int] access — mirrors sqlite3.Row."""

    def __init__(self, items):
        items = list(items)
        super().__init__(items)
        self._order = [k for k, _ in items]

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._order[key])
        return super().__getitem__(key)


def _hybrid_row(cursor):
    """psycopg3 row factory that returns _HybridRow instances."""
    if cursor.description is None:
        return None
    cols = [c.name for c in cursor.description]

    def make_row(values):
        return _HybridRow(zip(cols, values))

    return make_row


# ── PostgreSQL connection wrapper ─────────────────────────

class _PgConnection:
    """Wraps psycopg connection to mimic sqlite3.Connection interface."""

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def execute(self, sql, params=None):
        sql = _translate_sql(sql)
        if params is not None:
            return self._conn.execute(sql, params)
        return self._conn.execute(sql)

    def executescript(self, sql):
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if stmt and not stmt.upper().startswith('PRAGMA'):
                self._conn.execute(stmt)

    def commit(self):
        self._conn.commit()

    def close(self):
        if self._conn is not None:
            try:
                self._conn.rollback()
            except Exception:
                pass
            self._pool.putconn(self._conn)
            self._conn = None


# ── Public functions ──────────────────────────────────────

def _get_pg_pool():
    global _pool
    if _pool is None:
        import psycopg_pool

        def _configure(conn):
            conn.row_factory = _hybrid_row

        _pool = psycopg_pool.ConnectionPool(
            DB_URL,
            open=True,
            min_size=5,
            max_size=20,
            timeout=10,
            configure=_configure,
            kwargs={"options": "-c statement_timeout=10000"},
        )
        # Auto-create tables on first pool init (idempotent)
        conn = _pool.getconn()
        try:
            for stmt in SCHEMA_SQL_PG.split(';'):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.commit()
        finally:
            _pool.putconn(conn)
    return _pool


def get_connection(db_path=None):
    if _is_pg() and db_path is None:
        pool = _get_pg_pool()
        conn = pool.getconn()
        return _PgConnection(conn, pool)
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    if _is_pg() and db_path is None:
        # _get_pg_pool() already creates the schema on first call (idempotent).
        # Just return an open connection — no redundant schema SQL.
        return get_connection()
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    # Migrate existing SQLite DBs: add sla_set_at_ns if missing
    if db_path != ":memory:":
        try:
            conn.execute("SELECT sla_set_at_ns FROM sellers LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE sellers ADD COLUMN sla_set_at_ns INTEGER")
            conn.commit()
    return conn
