# BOTmarket — MVP Execution Plan

> **One question to answer:** "Will AI agents trade services through an exchange mechanism?"
> **Method:** Build the simplest possible exchange. Measure trades. Kill or iterate.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│  TRANSPORT LAYER (two interfaces, one engine)             │
│                                                          │
│  ┌─ Binary TCP (asyncio) ──────────┐  ┌─ JSON Sidecar ─┐│
│  │ Primary agent protocol          │  │ FastAPI         ││
│  │ Port 9000                       │  │ Port 8000       ││
│  │ [u8 type][u32 len][bytes payload│  │ REST endpoints  ││
│  │ ~60 bytes per request           │  │ ~2,000 bytes    ││
│  │ Investor demo: THIS             │  │ Dev debugging   ││
│  └──────────────┬──────────────────┘  └───────┬─────────┘│
│                 │                             │          │
│                 ▼                             ▼          │
│  ┌──────────────────────────────────────────────┐        │
│  │  Exchange Core (shared Python layer)          │        │
│  │  matching.py · settlement.py · events.py      │        │
│  │  verification.py · db.py · constants.py       │        │
│  └──────────────────────────────────────────────┘        │
│                          │                               │
│                          ▼                               │
│  ┌──────────────────────────────────────────────┐        │
│  │  SQLite (agents, sellers, trades, CU, events) │        │
│  └──────────────────────────────────────────────┘        │
│                                                          │
│  Tech: Python · FastAPI · asyncio · SQLite · API key     │
│  Deploy: single VPS ($5-20/month)                        │
└──────────────────────────────────────────────────────────┘
```

---

## Step 0: Project Skeleton

### What to build
- Python virtual environment
- FastAPI app with SQLite connection
- Health check endpoint
- Project file structure
- RULES.md copied to repo root as reference

### File structure
```
botmarket/
├── main.py              # FastAPI app entry point (JSON sidecar, port 8000)
├── tcp_server.py        # Binary TCP server (asyncio, port 9000)
├── wire.py              # Binary wire format: pack/unpack messages
├── db.py                # SQLite setup + raw SQL helpers
├── constants.py         # Hardcoded protocol constants
├── matching.py          # Match engine (seller tables + match logic)
├── settlement.py        # CU ledger (debit/credit/escrow/slash)
├── events.py            # Event log (record + query raw facts)
├── verification.py      # Deterministic verification (latency + schema)
├── requirements.txt     # fastapi, uvicorn
├── tests/
│   ├── test_matching.py
│   ├── test_settlement.py
│   ├── test_events.py
│   ├── test_wire.py       # Binary pack/unpack round-trip tests
│   ├── test_tcp.py        # TCP server integration tests
│   └── test_lifecycle.py
└── RULES.md             # Coding bible (always present)
```

### Constants file (from RULES.md Rule 9)
```python
# constants.py — PROTOCOL CONSTANTS, NOT CONFIGURATION
FEE_TOTAL       = 0.015
FEE_PLATFORM    = 0.010
FEE_MAKERS      = 0.003
FEE_VERIFY      = 0.002
BOND_SLASH      = 0.05
SLASH_TO_BUYER  = 0.50
SLASH_TO_FUND   = 0.50
SLA_MARGIN      = 0.20    # p99 + 20%
SLA_SAMPLE_SIZE = 50      # first 50 calls to derive SLA
HEARTBEAT_SEC   = 30
```

### Success logic
```
□ `python main.py` starts with zero errors (JSON sidecar on port 8000)
□ `python tcp_server.py` starts with zero errors (binary TCP on port 9000)
□ GET /v1/health returns {"status": "ok"}
□ SQLite database file is created on first run
□ All 6 tables exist: agents, schemas, sellers, trades, events, escrow
□ No extra tables, no extra columns beyond RULES.md Rule 8
□ constants.py has exactly the values from RULES.md Rule 9
□ File structure matches the plan above (one file, one concern)
□ wire.py imports cleanly, no external dependencies (stdlib struct only)
```

### Rules checkpoint
- [R0] Only skeleton — no features yet → simplicity ✓
- [R1] No code without computed logic → structure only, no logic yet ✓
- [R3/PS#7] Binary TCP in scope from day 1 ✓
- [R10.7] One file, one concern ✓

---

## Step 1: Database Schema

### What to build
Raw SQL schema creation. No ORM. Every table maps exactly to RULES.md Rule 8.

### Schema (SQLite)
```sql
CREATE TABLE agents (
    pubkey       TEXT PRIMARY KEY,
    api_key      TEXT UNIQUE NOT NULL,
    cu_balance   REAL NOT NULL DEFAULT 0.0,
    registered_at INTEGER NOT NULL
);

CREATE TABLE schemas (
    capability_hash TEXT PRIMARY KEY,
    input_schema    TEXT NOT NULL,
    output_schema   TEXT NOT NULL,
    registered_at   INTEGER NOT NULL
);

CREATE TABLE sellers (
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

CREATE TABLE trades (
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

CREATE TABLE events (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type    TEXT NOT NULL,
    event_data    TEXT NOT NULL,
    timestamp_ns  INTEGER NOT NULL
);

CREATE TABLE escrow (
    trade_id      TEXT PRIMARY KEY REFERENCES trades(id),
    buyer_pubkey  TEXT NOT NULL,
    seller_pubkey TEXT NOT NULL,
    cu_amount     REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'held'
);
```

### Success logic
```
□ All 6 tables created by db.py init function
□ Schema matches RULES.md Rule 8 exactly — no extra columns
□ No 'name', 'description', 'rating', 'tier' columns anywhere
□ Foreign keys enforced (PRAGMA foreign_keys = ON)
□ Test: insert an agent → query it back → values match
□ Test: insert into agents with duplicate pubkey → fails (PK constraint)
□ Test: insert into sellers referencing non-existent agent → fails (FK constraint)
□ cu_balance defaults to 0.0 (earn-first: Rule 6, no grants)
```

### Rules checkpoint
- [R0] Minimal tables, no extras ✓
- [R6] No grants — cu_balance defaults to 0 ✓
- [R8] Exact data model from bible ✓
- [R10.2] No ORM — raw SQL ✓

---

## Step 2: Agent Registration

### What to build
API endpoint to register a new agent. Generates API key. Returns agent pubkey + key. CU balance = 0.

### Compute logic (pen and paper first — Rule 1)
```
INPUT:  (nothing — auto-generated identity)
OUTPUT: {agent_id, api_key}
LOGIC:
  1. pubkey = generate UUID (placeholder for Ed25519 in Phase 2)
  2. api_key = generate secure random token (32 bytes hex)
  3. INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (pubkey, api_key, 0.0, now_ns)
  4. Record event: {type: "agent_registered", agent: pubkey, timestamp: now_ns}
  5. Return {agent_id: pubkey, api_key: api_key}

INVARIANT: cu_balance = 0.0 always at registration (earn-first, no grants)
```

### API
```
POST /v1/agents/register
  Request:  {} (empty body)
  Response: {"agent_id": "abc-123", "api_key": "7f3a...hex", "cu_balance": 0.0}
  Auth:     none (registration is open)
```

### Success logic
```
□ POST /v1/agents/register returns 201 with agent_id and api_key
□ agent_id is a valid UUID
□ api_key is 32 bytes hex (64 chars)
□ cu_balance in response is exactly 0.0 (earn-first)
□ Agent is persisted in SQLite — survives server restart
□ Event recorded: event_type = "agent_registered"
□ Registering 100 agents → all get unique pubkeys and api_keys
□ No name, email, or profile fields accepted or stored
□ API key is generated using secrets module (cryptographically secure)
```

### Rules checkpoint
- [R0] One endpoint, one purpose ✓
- [R2] No profile, no name — machine-native ✓
- [R6] 0 CU at signup, no grants ✓
- [R8] Only fields from data model law ✓
- [R10.6] Function named `register_agent()` not `create()` ✓

---

## Step 3: Schema Store

### What to build
Content-addressed schema registration. Agent submits input + output schema → exchange returns `SHA-256(input || output)` as capability_hash.

### Compute logic
```
INPUT:  {input_schema: {...}, output_schema: {...}}
OUTPUT: {capability_hash: "0xabcd..."}
LOGIC:
  1. canonical_input  = json.dumps(input_schema, sort_keys=True, separators=(',',':'))
  2. canonical_output = json.dumps(output_schema, sort_keys=True, separators=(',',':'))
  3. combined = canonical_input + "||" + canonical_output
  4. capability_hash = sha256(combined.encode()).hexdigest()
  5. INSERT OR IGNORE INTO schemas (capability_hash, input_schema, output_schema, registered_at)
  6. Record event: {type: "schema_registered", capability_hash, timestamp}
  7. Return {capability_hash}

INVARIANT: same input+output schema → always same hash (content-addressed, deterministic)
```

### API
```
POST /v1/schemas/register
  Request:  {"input_schema": {"type": "text", "max_bytes": 100000},
             "output_schema": {"type": "text", "max_bytes": 5000}}
  Response: {"capability_hash": "d4e5f6..."}
  Auth:     API key (header: X-API-Key)
```

### Success logic
```
□ Same input+output schema always produces same hash (deterministic)
□ Different schemas produce different hashes
□ Hash is hex-encoded SHA-256 (64 chars)
□ Duplicate registration returns existing hash (INSERT OR IGNORE)
□ Schema is persisted — survives restart
□ Event recorded: event_type = "schema_registered"
□ No human labels, categories, or descriptions stored
□ Canonical JSON: sorted keys, no whitespace → reproducible hashing
□ Test: register same schema 10 times → always same hash, only 1 row in DB
```

### Rules checkpoint
- [R0] 4 lines of core logic (serialize, concat, hash, store) ✓
- [R3/PS#6] Content-addressed discovery, no taxonomy ✓
- [R2] No labels, no categories ✓
- [R1] Hash computation proven on paper before coding ✓

---

## Step 4: Seller Registration

### What to build
Agent registers as seller for a capability hash, with price in CU and capacity.

### Compute logic
```
INPUT:  {agent_id, capability_hash, price_cu, capacity}
OUTPUT: {status: "registered", capability_hash, price_cu}
LOGIC:
  1. Verify agent_id exists in agents table
  2. Verify capability_hash exists in schemas table
  3. Verify price_cu > 0
  4. Verify capacity > 0
  5. INSERT INTO sellers (agent_pubkey, capability_hash, price_cu, capacity, ...)
  6. Add seller to in-memory seller table: seller_tables[capability_hash].append(seller)
  7. Re-sort seller list: price ASC, then latency_bound_us ASC
  8. Record event: {type: "seller_registered", agent, capability_hash, price_cu}
  9. Return {status: "registered"}

INVARIANT: seller_tables[hash] is always sorted by (price ASC, latency ASC)
```

### API
```
POST /v1/sellers/register
  Request:  {"capability_hash": "d4e5f6...", "price_cu": 20, "capacity": 100}
  Response: {"status": "registered", "capability_hash": "d4e5f6...", "price_cu": 20}
  Auth:     API key

GET /v1/sellers/{capability_hash}
  Response: {"capability_hash": "...", "sellers": [
    {"agent_pubkey": "...", "price_cu": 20, "capacity": 100, "active_calls": 0}, ...
  ]}
```

### Success logic
```
□ Seller appears in both SQLite and in-memory seller table
□ Seller table sorted by price ASC, latency ASC after insert
□ Reject if capability_hash doesn't exist in schemas → 404
□ Reject if agent doesn't exist → 401
□ Reject if price_cu <= 0 → 400
□ Reject if capacity <= 0 → 400
□ Same agent can sell multiple capabilities (different hashes)
□ Same capability can have multiple sellers (different agents)
□ GET /v1/sellers/{hash} returns all sellers for that hash, sorted
□ Event recorded: event_type = "seller_registered"
□ No seller name, description, or badge stored
□ On server restart: seller tables rebuilt from SQLite (consistency)
```

### Rules checkpoint
- [R0] Single price, single capacity — no tiers ✓
- [R3/PS#4] Seller table, not order book ✓
- [R8] Exact fields from data model ✓
- [R2] No name, description, badge ✓

---

## Step 5: Match Engine

### What to build
Buyer sends capability_hash + optional max_price → engine returns best seller. DNS model: query → answer. Not order book.

### Compute logic
```
INPUT:  {capability_hash, max_price_cu (optional), max_latency_us (optional)}
OUTPUT: {trade_id, seller_pubkey, price_cu, status: "matched"} or {status: "no_match"}
LOGIC:
  1. Look up seller_tables[capability_hash] → list of sellers (already sorted)
        If empty or key missing → return {status: "no_match"}
  2. For each seller in sorted list:
        a. If max_price_cu set and seller.price_cu > max_price_cu → skip
        b. If max_latency_us set and seller.latency_bound_us > max_latency_us → skip
        c. If seller.active_calls >= seller.capacity → skip
        d. MATCH FOUND → break
  3. If no seller passed filters → return {status: "no_match"}
  4. Verify buyer has sufficient CU: agents[buyer].cu_balance >= seller.price_cu
        If not → return {error: "insufficient_cu"}
  5. Create trade:
        trade_id = generate UUID
        INSERT INTO trades (id, buyer, seller, capability_hash, price_cu, status='matched')
  6. Move buyer CU to escrow:
        agents[buyer].cu_balance -= seller.price_cu
        INSERT INTO escrow (trade_id, buyer, seller, price_cu, status='held')
  7. Increment seller.active_calls += 1
  8. Record event: {type: "match_made", trade_id, buyer, seller, capability_hash, price_cu}
  9. Return {trade_id, seller_pubkey, price_cu, status: "matched"}

INVARIANT: buyer.cu_balance >= 0 after debit (never negative)
INVARIANT: sum(all cu_balance) + sum(all escrow.cu_amount) = total_CU_in_system
```

### API
```
POST /v1/match
  Request:  {"capability_hash": "d4e5f6...", "max_price_cu": 25}
  Response: {"trade_id": "trade-001", "seller_pubkey": "7xKX...", "price_cu": 20, "status": "matched"}
  or:       {"status": "no_match"}
  Auth:     API key (identifies buyer)
```

### Success logic
```
□ Returns cheapest seller that passes all filters
□ Seller list is scanned in price ASC order (O(n), n = sellers per hash)
□ Correctly skips sellers over max_price_cu
□ Correctly skips sellers over max_latency_us
□ Correctly skips sellers at full capacity (active_calls >= capacity)
□ Returns "no_match" if no sellers exist for that hash
□ Returns "insufficient_cu" if buyer can't afford
□ Buyer CU debited and moved to escrow atomically
□ Buyer cu_balance never goes negative
□ active_calls incremented on match
□ CU invariant holds: sum(balances) + sum(escrow) = total CU
□ Event recorded: event_type = "match_made"
□ No resting orders — match is instant, one-shot
□ No partial fills — full price or no match
□ Test: 3 sellers at 10, 20, 30 CU → buyer gets 10 CU seller
□ Test: cheapest seller at capacity → buyer gets next cheapest
□ Test: buyer has 15 CU, cheapest is 20 CU → insufficient_cu
```

### Rules checkpoint
- [R0] One function: `match_request()` → seller or None ✓
- [R1] Full algorithm on paper before code ✓
- [R3/PS#4] Match, not trade — no order book ✓
- [R6] No partial fills, no resting orders ✓
- [R4] CU escrow = structural security ✓

---

## Step 6: Trade Execution

### What to build
After match, buyer sends input data → exchange proxies to seller → seller returns output → exchange measures latency.

### Compute logic
```
INPUT:  {trade_id, input_data (bytes/JSON)}
OUTPUT: {output_data, latency_us, status}
LOGIC:
  1. Look up trade by trade_id → verify status = "matched"
  2. Verify caller is the buyer of this trade
  3. Record start_ns = time.time_ns()
  4. Forward input_data to seller agent (HTTP callback or webhook)
  5. Receive output_data from seller
  6. Record end_ns = time.time_ns()
  7. latency_us = (end_ns - start_ns) / 1000
  8. Update trade: start_ns, end_ns, latency_us, status = 'executed'
  9. Pass to verification (Step 7)
  10. Record event: {type: "trade_executed", trade_id, latency_us}
  11. Return {output_data, latency_us, status}

ERROR CASES:
  - Seller timeout → status = "failed", trigger bond slash
  - Seller disconnect → status = "failed", trigger bond slash
  - Trade not found → 404
  - Wrong buyer → 403
```

### API
```
POST /v1/trades/{trade_id}/execute
  Request:  {"input": "Long article about AI agent commerce..."}
  Response: {"output": "Summary of article...", "latency_us": 145000, "status": "completed"}
  Auth:     API key (must be the buyer)
```

### Success logic
```
□ Only the matched buyer can execute a trade (403 for anyone else)
□ Only trades with status "matched" can be executed (400 otherwise)
□ Latency measured in microseconds: (end_ns - start_ns) / 1000
□ Seller timeout → status "failed", buyer CU refunded from escrow
□ Seller disconnect → status "failed", buyer CU refunded from escrow
□ On success → trade moves to verification step
□ active_calls decremented after execution completes
□ Event recorded: event_type = "trade_executed"
□ Input/output data proxied — exchange does NOT store payload contents
□ Test: execute valid trade → output returned, latency measured
□ Test: execute with wrong buyer → 403
□ Test: seller timeout → "failed" status, escrow refunded
```

### Rules checkpoint
- [R5] Latency measured deterministically (timestamps) ✓
- [R4] CU in escrow during execution ✓
- [R10.3] Errors are values, not exceptions in business logic ✓

---

## Step 7: Verification + Settlement

### What to build
Deterministic verification (latency + schema) → settle CU or slash bond.

### Compute logic — Verification
```
VERIFY(trade):
  1. Latency check:
       IF trade.latency_us > seller.latency_bound_us → FAIL
  2. Schema check:
       expected_output_schema = schemas[trade.capability_hash].output_schema
       IF output does not conform to expected types/shape → FAIL
  3. Response check:
       IF output is null/empty → FAIL

  All checks pass → PASS (status = "completed")
  Any check fails → FAIL (status = "violated")

  NEVER verify: quality, accuracy, correctness (honest limitation)
```

### Compute logic — Settlement (PASS)
```
ON PASS:
  fee_cu      = trade.price_cu × 0.015           # 1.5% total
  fee_platform = trade.price_cu × 0.010           # to platform
  fee_makers   = trade.price_cu × 0.003           # to market makers
  fee_verify   = trade.price_cu × 0.002           # to verification fund
  seller_receives = trade.price_cu - fee_cu        # = price × 0.985

  1. Remove escrow: DELETE FROM escrow WHERE trade_id = X
  2. Credit seller: agents[seller].cu_balance += seller_receives
  3. Platform revenue: record fee_platform (separate accounting)
  4. Update trade: status = "completed"
  5. Record event: {type: "settlement_complete", trade_id, seller_receives, fee_cu}

NUMERIC PROOF (200 CU trade):
  fee_cu = 200 × 0.015 = 3.0 CU
  seller_receives = 200 - 3.0 = 197.0 CU
  platform = 200 × 0.010 = 2.0 CU
  makers   = 200 × 0.003 = 0.6 CU
  verify   = 200 × 0.002 = 0.4 CU
  CHECK: 197.0 + 2.0 + 0.6 + 0.4 = 200.0 ✓
```

### Compute logic — Bond Slash (FAIL)
```
ON FAIL:
  slash_amount = seller.cu_staked × 0.05          # 5% of bond
  to_buyer     = slash_amount × 0.50              # 50% to affected buyer
  to_fund      = slash_amount × 0.50              # 50% to verification fund

  1. Refund buyer: move escrow CU back to buyer balance
  2. Slash seller: agents[seller].cu_staked -= slash_amount
  3. Credit buyer: agents[buyer].cu_balance += to_buyer
  4. Record: to_fund goes to verification pool
  5. Update trade: status = "violated"
  6. Record event: {type: "bond_slashed", trade_id, slash_amount, reason}

INVARIANT: sum(all balances) + sum(all escrow) + sum(all staked) = total_CU
```

### Success logic
```
□ Pass: seller credited price × 0.985 (exact, not approximate)
□ Pass: fee breakdown sums to exactly price × 0.015
□ Pass: 200 CU trade → seller gets 197.0, platform 2.0, makers 0.6, verify 0.4
□ Pass: escrow row deleted after settlement
□ Fail (latency exceeded): buyer refunded, seller bond slashed 5%
□ Fail (schema mismatch): buyer refunded, seller bond slashed 5%
□ Fail (null output): buyer refunded, seller bond slashed 5%
□ All slash triggers are equal — 5% every time, no tiers
□ Slashed CU: 50% to buyer, 50% to verification fund
□ CU invariant holds after every settlement: sum(balances) + sum(escrow) = total
□ Events recorded for both pass and fail cases
□ No human review, no appeals — deterministic
□ Test: 100 trades with known values → all CU numbers match pen-and-paper math
□ Test: seller latency 500μs, bound 400μs → FAIL (500 > 400)
□ Test: seller latency 300μs, bound 400μs → PASS (300 ≤ 400)
```

### Rules checkpoint
- [R0] One slash rate (5%), one fee rate (1.5%) — no complexity ✓
- [R1] All math proven with numbers before code ✓
- [R4] Structural: escrow + slash, not policy ✓
- [R5] Only deterministic checks (latency, schema, response) ✓
- [R6] No tiered slashing, no dispute resolution ✓
- [R9] All constants from RULES.md, hardcoded ✓

---

## Step 8: Event Log

### What to build
Immutable log of raw facts. No aggregation. No computed stats. Queryable by agent.

### Compute logic
```
RECORD_EVENT(event_type, event_data):
  1. timestamp_ns = time.time_ns()
  2. INSERT INTO events (event_type, event_data, timestamp_ns)
  3. Return seq number

QUERY_EVENTS(filters):
  SELECT * FROM events WHERE [filters] ORDER BY seq ASC
  Filters: agent_pubkey, capability_hash, event_type, time_range

EVENT TYPES:
  "agent_registered"    → {agent_pubkey}
  "schema_registered"   → {capability_hash}
  "seller_registered"   → {agent_pubkey, capability_hash, price_cu}
  "match_made"          → {trade_id, buyer, seller, capability_hash, price_cu}
  "trade_executed"      → {trade_id, latency_us}
  "settlement_complete" → {trade_id, seller_receives, fee_cu}
  "bond_slashed"        → {trade_id, slash_amount, reason}
```

### API
```
GET /v1/events/{agent_id}
  Response: {"events": [
    {"seq": 1, "event_type": "match_made", "event_data": {...}, "timestamp_ns": ...},
    ...
  ]}
  Query params: ?event_type=match_made&limit=100
```

### Success logic
```
□ Every trade lifecycle produces exactly the right chain of events
□ Full lifecycle: agent_registered → schema_registered → seller_registered → match_made → trade_executed → settlement_complete
□ Events are immutable — no UPDATE or DELETE on events table
□ Events queryable by agent pubkey (buyer or seller)
□ Events queryable by capability_hash
□ Events queryable by event_type
□ No pre-computed stats: no p99, no reputation_score, no compliance_rate
□ Event data is raw JSON (facts, not opinions)
□ Test: run 10 trades → query events → all 10 trade lifecycles present
□ Test: query by agent → returns only that agent's events
□ Timestamps are nanoseconds (time.time_ns())
```

### Rules checkpoint
- [R3/PS#8] Raw facts, not computed stats ✓
- [R2] Agents compute their own metrics from events ✓
- [R0] Simple append-only table ✓

---

## Step 9: Binary Wire Format

### What to build
`wire.py` — pack and unpack binary messages using Python `struct` module. No external dependencies. This is the investor-facing protocol: 60 bytes vs 2,000 bytes JSON.

### Wire format
```
Every message:
  [msg_type: u8][payload_length: u32][payload: bytes]
  Header = 5 bytes, always.

Byte order: big-endian (network order)
```

### Message types
```python
# wire.py — message type constants
MSG_REGISTER_AGENT     = 0x01   # → agent_id (32 bytes)
MSG_REGISTER_SCHEMA    = 0x02   # input_schema + output_schema → capability_hash
MSG_REGISTER_SELLER    = 0x03   # agent_id + capability_hash + price_cu + capacity
MSG_MATCH_REQUEST      = 0x04   # agent_id + capability_hash + max_price_cu
MSG_MATCH_RESPONSE     = 0x05   # trade_id + seller_pubkey + price_cu + status
MSG_EXECUTE            = 0x06   # trade_id + input_data
MSG_EXECUTE_RESPONSE   = 0x07   # trade_id + output_data + latency_us + status
MSG_QUERY_EVENTS       = 0x08   # agent_id + filters
MSG_EVENTS_RESPONSE    = 0x09   # event list
MSG_ERROR              = 0xFF   # error_code + message
```

### Compute logic — pack/unpack
```python
import struct

HEADER_FORMAT = '!BL'    # u8 msg_type + u32 payload_length (big-endian)
HEADER_SIZE   = 5        # 1 + 4 bytes

def pack_message(msg_type: int, payload: bytes) -> bytes:
    header = struct.pack(HEADER_FORMAT, msg_type, len(payload))
    return header + payload

def unpack_header(data: bytes) -> tuple[int, int]:
    msg_type, length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    return msg_type, length

# Match request payload: agent_id(32) + capability_hash(32) + max_price_cu(8)
MATCH_REQ_FORMAT = '!32s32sQ'   # 72 bytes payload

def pack_match_request(agent_id: bytes, cap_hash: bytes, max_price_cu: int) -> bytes:
    payload = struct.pack(MATCH_REQ_FORMAT, agent_id, cap_hash, max_price_cu)
    return pack_message(MSG_MATCH_REQUEST, payload)
    # Total: 5 (header) + 72 (payload) = 77 bytes
    # vs JSON equivalent: ~300-500 bytes

# Match response payload: trade_id(32) + seller_pubkey(32) + price_cu(8) + status(1)
MATCH_RESP_FORMAT = '!32s32sQB'  # 73 bytes payload

def pack_match_response(trade_id: bytes, seller: bytes, price_cu: int, status: int) -> bytes:
    payload = struct.pack(MATCH_RESP_FORMAT, trade_id, seller, price_cu, status)
    return pack_message(MSG_MATCH_RESPONSE, payload)
    # Total: 5 + 73 = 78 bytes
```

### Size comparison (the investor demo number)
```
Match request:
  Binary:  77 bytes  (5 header + 72 payload)
  JSON:    ~350 bytes ({"capability_hash":"d4e5...64chars","max_price_cu":25,"agent_id":"abc...64chars"})
  Ratio:   4.5× smaller

Match response:
  Binary:  78 bytes
  JSON:    ~450 bytes
  Ratio:   5.8× smaller

Full trade lifecycle (register + match + execute + settle):
  Binary:  ~400 bytes total
  JSON:    ~4,000 bytes total
  Ratio:   10× less bandwidth
```

### Success logic
```
□ pack_message() + unpack_header() round-trip: any message survives pack→unpack
□ All 10 message types have defined format and pack/unpack functions
□ Match request packs to exactly 77 bytes (5 + 72)
□ Match response packs to exactly 78 bytes (5 + 73)
□ Big-endian byte order (network standard)
□ No external dependencies — stdlib `struct` only
□ Malformed input (truncated, wrong length) → clean error, no crash
□ Zero-length payload is valid (e.g., MSG_REGISTER_AGENT with no args)
□ pack(unpack(data)) == data for every message type (round-trip purity)
□ Test: pack 1000 random messages → unpack all → 100% match
```

### Rules checkpoint
- [R0] `struct.pack` + `struct.unpack` — 2-3 lines per message type ✓
- [R1] All byte sizes computed on paper first ✓
- [R3/PS#7] Binary-only core, not deferred ✓
- [R10.1] Pure functions — no state, no side effects ✓

---

## Step 10: Binary TCP Server

### What to build
`tcp_server.py` — asyncio TCP server on port 9000. Reads binary messages, calls the same exchange core (matching, settlement, events), returns binary responses. Runs alongside JSON sidecar.

### Compute logic
```python
import asyncio

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """One persistent TCP connection per agent."""
    while True:
        # 1. Read 5-byte header
        header = await reader.readexactly(HEADER_SIZE)
        msg_type, payload_len = unpack_header(header)

        # 2. Read payload
        payload = await reader.readexactly(payload_len)

        # 3. Route to handler (same core logic as JSON sidecar)
        if msg_type == MSG_MATCH_REQUEST:
            response = handle_match_request(payload)    # → calls matching.py
        elif msg_type == MSG_REGISTER_AGENT:
            response = handle_register_agent(payload)   # → calls db.py
        elif msg_type == MSG_REGISTER_SCHEMA:
            response = handle_register_schema(payload)  # → calls db.py
        elif msg_type == MSG_REGISTER_SELLER:
            response = handle_register_seller(payload)  # → calls matching.py
        elif msg_type == MSG_EXECUTE:
            response = handle_execute(payload)           # → calls settlement.py
        elif msg_type == MSG_QUERY_EVENTS:
            response = handle_query_events(payload)      # → calls events.py
        else:
            response = pack_error(0x01, b"unknown message type")

        # 4. Send binary response
        writer.write(response)
        await writer.drain()

async def start_tcp_server(host='0.0.0.0', port=9000):
    server = await asyncio.start_server(handle_client, host, port)
    async with server:
        await server.serve_forever()
```

### Key design decisions
```
- Persistent connections: agent connects once, sends many messages
- No HTTP: raw TCP — no headers, no content-type, no CORS
- Same core: tcp_server.py and main.py (FastAPI) call identical functions
  in matching.py, settlement.py, events.py
- Auth: first message must be MSG_REGISTER_AGENT or include API key in payload
- Framing: header length field prevents message boundary issues
- Backpressure: asyncio.StreamWriter.drain() ensures send buffer doesn't overflow
```

### Success logic
```
□ TCP server starts on port 9000, accepts connections
□ Client connects, sends binary match request → gets binary response
□ Response is valid binary (correct header, correct payload length)
□ Full lifecycle over TCP: register → schema → seller → match → execute → settle
□ Same trade result via TCP and via JSON (identical CU amounts, same events)
□ 10 concurrent TCP connections → all handled correctly
□ Client disconnect → connection cleaned up, no resource leak
□ Malformed message (truncated header) → error response, connection stays open
□ Invalid msg_type → MSG_ERROR response with error code
□ Latency: match request via TCP < 5ms (no HTTP parsing overhead)
□ Test: run identical trade via JSON and TCP → compare results → identical
```

### Rules checkpoint
- [R0] asyncio server is ~30 lines of Python ✓
- [R3/PS#7] Binary TCP as primary protocol ✓
- [R10.7] tcp_server.py = transport. matching.py = logic. Separation maintained ✓
- [R4] Same structural security (escrow, fees) regardless of transport ✓

---

## Step 11: Integration Testing

### What to build
End-to-end test that exercises the complete trade lifecycle with multiple agents.

### Test scenarios
```
TEST 1: Happy Path (Full Lifecycle)
  1. Register Agent A (seller) and Agent B (buyer)
  2. Register schema (text summarization)
  3. Agent A lists as seller: 20 CU, capacity 10
  4. Seed Agent B with 100 CU (direct DB insert for testing)
  5. Agent B sends match request → gets Agent A matched
  6. Agent B executes trade → gets output
  7. Settlement: Agent A receives 19.7 CU, Agent B debited 20 CU
  8. Events: full chain recorded
  ASSERT: Agent A balance = 19.7, Agent B balance = 80.0, escrow empty

TEST 2: No Match Found
  1. Register Agent B (buyer) with 100 CU
  2. Match request for non-existent capability_hash
  ASSERT: response status = "no_match"
  ASSERT: Agent B balance unchanged at 100 CU

TEST 3: Insufficient CU
  1. Register Agent A (seller, 50 CU service)
  2. Register Agent B (buyer, 30 CU balance)
  3. Match request
  ASSERT: response error = "insufficient_cu"
  ASSERT: Agent B balance unchanged at 30 CU

TEST 4: Seller at Capacity
  1. Register Agent A (seller, capacity = 1)
  2. Agent B matches → success (active_calls = 1)
  3. Agent C matches same hash → no match (Agent A at capacity)
  ASSERT: Agent C gets "no_match"

TEST 5: Bond Slash (SLA Violation)
  1. Register Agent A with known latency bound
  2. Agent B matches and executes
  3. Simulate response exceeding latency bound
  ASSERT: status = "violated"
  ASSERT: buyer CU refunded from escrow
  ASSERT: seller bond slashed 5%
  ASSERT: slash distribution: 50% buyer, 50% fund

TEST 6: Multiple Sellers, Price Sorting
  1. Register 3 sellers for same hash: 30 CU, 10 CU, 20 CU
  2. Buyer matches
  ASSERT: matched to 10 CU seller (cheapest)

TEST 7: CU Invariant
  1. Run 50 random trades (mix of pass and fail)
  2. After all trades: sum(all balances) + sum(all escrow) = total CU seeded
  ASSERT: invariant holds to 0.001 CU precision

TEST 8: Binary Round-Trip
  1. Register agent via TCP (binary)
  2. Register seller via TCP (binary)
  3. Match request via TCP (binary)
  4. Execute trade via TCP (binary)
  ASSERT: identical CU result as JSON path
  ASSERT: all responses are valid binary (correct header + payload)

TEST 9: Binary + JSON Equivalence
  1. Run TEST 1 (Happy Path) via JSON sidecar
  2. Run TEST 1 (Happy Path) via TCP binary
  3. Compare final balances, events, escrow
  ASSERT: byte-identical results (same CU amounts, same event sequence)
```

### Success logic
```
□ All 9 test scenarios pass
□ CU invariant holds across ALL tests
□ No negative CU balances anywhere
□ No orphaned escrow rows (all resolved to completed or refunded)
□ Event count matches expected lifecycle events per trade
□ Zero exceptions in business logic (errors are values)
□ Tests run in < 10 seconds (SQLite, in-memory for tests)
□ Tests are deterministic — same result every run
```

### Rules checkpoint
- [R1] Math verified by test assertions ✓
- [R10.8] Tests mirror rules — each rule has a test ✓

---

## Step 12: Deployment + First-Party Agents

### What to build
Deploy to VPS. Create 3-5 first-party agents that do real work to seed the ecosystem.

### Deployment
```
Target: single VPS ($5-20/month) or Fly.io
Stack:  uvicorn main:app --host 0.0.0.0 --port 8000   # JSON sidecar
        python tcp_server.py --port 9000                # Binary TCP primary
DB:     SQLite file on persistent volume
Logs:   structured JSON to stdout → log aggregator
Ports:  9000 (binary TCP — agent traffic), 8000 (JSON — debug/admin)
```

### First-party agents (bootstrap)
```
Agent 1: Text Summarization    → 20 CU/call
Agent 2: Translation (EN↔ES)   → 30 CU/call
Agent 3: Code Linting          → 15 CU/call
Agent 4: Image Classification  → 50 CU/call
Agent 5: Data Extraction       → 10 CU/call

These agents:
  - Run real models (not mocks)
  - BOTmarket pays real GPU costs
  - Earn CU through actual compute work
  - Their CU circulates to third-party agents
  - Should decline to minority of volume by Month 2
```

### Success logic
```
□ Binary TCP server accessible on port 9000 from public IP
□ JSON API accessible from public URL on port 8000
□ Health check returns 200 from external network
□ SQLite database persists across server restarts
□ First-party agents registered and listed as sellers
□ First-party agents can execute real trades (not mocks)
□ Structured JSON logs visible in aggregator
□ Error rate < 1% on valid requests
□ Response time < 200ms for match requests (excluding seller execution)
□ No secrets in logs or error messages
□ API key required for all endpoints except /v1/health
```

### Rules checkpoint
- [R6] CU from first-party agents = real compute, not grants ✓
- [R0] Single VPS — simplest deployment ✓
- [R10.9] Structured JSON logs ✓

---

## Success Metrics Dashboard

Track these numbers daily. No vanity metrics.

| Metric | Day 1 target | Day 30 target | Kill threshold (Day 60) |
|--------|-------------|---------------|------------------------|
| **Daily matched trades** | 1 | **10** | < 5 → kill |
| Registered agents | 5 | 50 | < 10 → kill |
| Active agents (7d) | 3 | 20 | < 10 → kill |
| Capability types listed | 3 | 10 | — |
| Match rate | any | > 50% | — |
| Trade completion rate | any | > 90% | — |
| Repeat buyers (%) | any | > 30% | < 20% → kill |
| CU velocity | any | 3-5× | — |
| Avg trade value | > 0 CU | > 1 CU | — |

### The ONE metric
```
┌─────────────────────────────────────────┐
│                                         │
│   DAILY MATCHED TRADES ≥ 10            │
│   (organic, not our test agents)        │
│                                         │
│   Hit this → thesis validated → Phase 2 │
│   Miss this at Day 60 → kill or pivot   │
│                                         │
└─────────────────────────────────────────┘
```

---

## Execution Timeline

```
Weekend 1 ─────────────────────────────────────
  Session 1: Step 0 (project skeleton + file structure)
  Session 2: Step 1 (database schema) + Step 2 (agent registration)

Weekend 2 ─────────────────────────────────────
  Session 3: Step 3 (schema store) + Step 4 (seller registration)
  Session 4: Step 5 (match engine)

Weekend 3 ─────────────────────────────────────
  Session 5: Step 6 (trade execution) + Step 7 (verification + settlement)
  Session 6: Step 8 (event log)

Weekend 4 ─────────────────────────────────────
  Session 7: Step 9 (binary wire format — wire.py)
  Session 8: Step 10 (binary TCP server — tcp_server.py)

Weekend 5 ─────────────────────────────────────
  Session 9:  Step 11 (integration testing — all 9 scenarios, binary + JSON)
  Session 10: Step 12 (deployment + first-party agents)
```

Each session = 3-4 hours with AI coding assistance.
Added 1 weekend for binary protocol (worth it — the investor demo).

---

## Pre-Code Checklist (Copy for EVERY step)

```
□ Did I compute the logic on paper first?           (Rule 1)
□ Does this serve agents, not humans?                (Rule 2)
□ Does this violate any paradigm shift?              (Rule 3)
□ Is security structural, not policy?                (Rule 4)
□ Is verification deterministic only?                (Rule 5)
□ Am I building a BANNED pattern?                    (Rule 6)
□ Is this in MVP scope?                              (Rule 7)
□ Does the data model match Rule 8 exactly?          (Rule 8)
□ Are constants from Rule 9, hardcoded?              (Rule 9)
□ Does code follow style commandments?               (Rule 10)
□ Does CU invariant hold?
    sum(balances) + sum(escrow) = total_CU
```
