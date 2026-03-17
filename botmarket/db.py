import sqlite3
import os

DB_PATH = os.environ.get("BOTMARKET_DB", "botmarket.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agents (
    pubkey        TEXT PRIMARY KEY,
    api_key       TEXT UNIQUE NOT NULL,
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
"""


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn
