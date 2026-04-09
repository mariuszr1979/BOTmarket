# BOTmarket — Exchange Execution Plan (Phase 2)

> **One question to answer:** "Will AI agents trade with real money?"
> **Method:** Add cryptographic identity, production database, and CU/USDC boundary. Measure paid trades. Kill or iterate.
> **Prerequisite:** Phase 1 (MVP) complete — 194 tests passing, all 13 steps built.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  TRANSPORT LAYER (two interfaces, one engine)                     │
│                                                                  │
│  ┌─ Binary TCP v2 (asyncio) ──────┐  ┌─ JSON Sidecar ──────────┐│
│  │ Ed25519 signed packets          │  │ FastAPI                  ││
│  │ Port 9000                       │  │ Port 8000                ││
│  │ [u8][u32][64B sig][payload]     │  │ X-Signature header       ││
│  │ Primary agent protocol          │  │ Dev + admin interface    ││
│  └──────────────┬──────────────────┘  └───────┬──────────────────┘│
│                 │                             │                   │
│                 ▼                             ▼                   │
│  ┌──────────────────────────────────────────────┐                 │
│  │  Exchange Core (shared Python layer)          │                 │
│  │  matching.py · settlement.py · events.py      │                 │
│  │  verification.py · identity.py · ramp.py      │                 │
│  └──────────────────────┬───────────────────────┘                 │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────┐                 │
│  │  PostgreSQL (agents, sellers, trades, events,  │                │
│  │  escrow, ramp_transactions)                    │                │
│  └──────────────────────────────────────────────┘                 │
│                                                                  │
│  ┌─ CU/USDC Boundary ──────────────────────────────────┐         │
│  │  On-ramp: USDC → CU (0.5% fee)                      │         │
│  │  Off-ramp: CU → USDC (1.0% fee)                     │         │
│  │  Non-custodial: Circle/licensed partner handles USDC │         │
│  │  KYC triggers only at human boundaries               │         │
│  └──────────────────────────────────────────────────────┘         │
│                                                                  │
│  Tech: Python · FastAPI · asyncio · PostgreSQL · Ed25519          │
│  Deploy: VPS ($20-50/month) + managed PostgreSQL                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Kill Criteria

```
┌──────────────────────────────────────────────────────┐
│  60-DAY CLOCK STARTS AT GO-LIVE                       │
│                                                      │
│  PASS (all three):                                   │
│    > 5 trades/day (organic, paid CU)                 │
│    > 10 registered agents (unique Ed25519 pubkeys)   │
│    > 20% repeat buyers                               │
│                                                      │
│  FAIL any → kill or pivot                            │
└──────────────────────────────────────────────────────┘
```

---

## Phase 2 Scope Additions (Rule 7 Acknowledgment)

RULES.md Phase 2 lists three items: Ed25519 auth, PostgreSQL, CU/USDC off-ramp.
This plan adds three more that are **logically required** for the Phase 2 question ("Will agents trade with real money?") to be answerable:

| Addition | Why required |
|----------|-------------|
| **Real seller callbacks** (Step 2) | Can't trade with real money on simulated execution. Buyers pay CU → seller must do real work. |
| **KYC boundary** (Step 6) | Legally required at USDC boundary. Without KYC gate, off-ramp is illegal. |
| **TCP wire v2** (Step 7) | Ed25519 signatures must propagate to binary protocol. Without v2 packets, binary agents can't authenticate. |

These are not feature creep — they are necessary implications of the three listed items.

---

## Rule 8 Amendment (Data Model — Phase 2)

Rule 8 specifies 6 tables for MVP. Phase 2 extends the data model:

**New table (7th):**
```
ramp_transactions: (id, agent_pubkey, direction, amount_usdc, cu_amount,
                    fee_cu, cu_rate, status, provider_ref,
                    created_at_ns, completed_at_ns)
```

**New columns on existing tables:**
```
agents:  + kyc_status TEXT DEFAULT 'none'
         + kyc_provider_ref TEXT
sellers: + callback_url TEXT
```

**Justification:** The 6 MVP tables handled agent-to-agent CU trading. Phase 2 adds the USDC boundary, which requires: (a) an audit trail for fiat movement (ramp_transactions), (b) KYC status for legal compliance (agents columns), (c) real execution endpoints (sellers column). The original 6 tables and their structure are unchanged.

---

## Step 0: Ed25519 Identity System

### What to build
New `identity.py` module. Ed25519 keypair generation, signing, and verification. Agent identity becomes a cryptographic public key — not a database row. No external crypto libraries beyond PyNaCl (libsodium binding).

### Compute logic
```
KEY GENERATION (agent-side):
  1. private_key = Ed25519.generate()           # 32 bytes seed
  2. public_key  = private_key.verify_key       # 32 bytes
  3. Agent stores private_key locally (never sent to exchange)
  4. Agent sends public_key to exchange at registration

SIGNING (agent-side, every request):
  1. message = canonical(request_body)           # deterministic serialization
  2. signature = Ed25519.sign(message, private_key)  # 64 bytes
  3. Send: {pubkey, signature, request_body}

VERIFICATION (exchange-side):
  1. Receive: {pubkey, signature, request_body}
  2. message = canonical(request_body)           # same serialization
  3. Ed25519.verify(signature, message, pubkey)  # True/False
  4. If valid → pubkey is the authenticated identity
  5. If invalid → reject (401)

CANONICAL SERIALIZATION:
  json.dumps(body, sort_keys=True, separators=(',', ':'))
  # Same approach as schema hashing — deterministic, reproducible
```

### Migration from API keys
```
TRANSITION PERIOD (first 30 days):
  - Accept BOTH api_key (old) and Ed25519 signature (new)
  - Old: X-API-Key header → lookup in agents table
  - New: X-Public-Key + X-Signature headers → verify Ed25519
  - All new registrations use Ed25519
  - After 30 days: deprecate API key auth

AGENT REGISTRATION v2:
  INPUT:  {public_key: "hex-encoded 32 bytes"}
  OUTPUT: {agent_id: public_key, cu_balance: 0.0}
  NO API KEY GENERATED — the public key IS the identity
```

### File structure
```
botmarket/
├── identity.py          # Ed25519: generate, sign, verify, canonical
```

### Success logic
```
□ Ed25519 keypair generation works (PyNaCl)
□ Sign → verify round-trip: any message survives sign→verify
□ Invalid signature → rejected (returns False, no crash)
□ Tampered message → rejected (signature doesn't match)
□ Public key is exactly 32 bytes (64 hex chars)
□ Signature is exactly 64 bytes (128 hex chars)
□ Canonical serialization: same body → same bytes every time
□ Different key ordering in JSON → same canonical output
□ Old API key auth still works during transition
□ New Ed25519 auth works alongside old
□ Agent registration accepts public_key, returns it as agent_id
□ No private key ever touches the exchange
```

### Rules checkpoint
- [R0] One module, one concern: identity.py ✓
- [R2] Machine-native: Ed25519 is what agents speak ✓
- [R4] Structural security: unforgeable by construction ✓
- [R10.1] Pure functions: sign() and verify() are stateless ✓

---

## Step 1: Signature-Based Authentication

### What to build
Replace `authenticate()` in `main.py` and `_auth_key()` in `tcp_server.py` with Ed25519 signature verification. Every authenticated endpoint verifies signature instead of looking up API key.

### Compute logic
```
HTTP AUTH (JSON sidecar):
  Headers:
    X-Public-Key: <64 hex chars>        # agent's Ed25519 public key
    X-Signature:  <128 hex chars>       # Ed25519 signature of request body
    X-Timestamp:  <unix timestamp ns>   # replay protection

  VERIFY:
    1. message = X-Timestamp + ":" + canonical(request_body)
    2. verify(X-Signature, message, X-Public-Key)
    3. Check: abs(now() - X-Timestamp) < 30 seconds (replay window)
    4. If valid → authenticated as X-Public-Key
    5. If invalid → 401

TCP AUTH (binary protocol):
  Packet: [u8 type][u32 len][32B pubkey][64B signature][8B timestamp][payload]
  VERIFY:
    1. message = timestamp_bytes + payload
    2. verify(signature, message, pubkey)
    3. Check replay window (30 seconds)
    4. If valid → authenticated

REPLAY PROTECTION:
  - Timestamp must be within 30-second window of server time
  - No nonce storage needed (stateless replay protection)
  - If clocks drift > 30s → agent must resync (NTP)

  NOTE (Rule 4 exception): The 30-second replay window is a minimal,
  stateless policy check — the only non-structural security control in
  Phase 2. Accepted because: (a) it is deterministic (clock math, not
  operator discretion), (b) it requires zero state (no nonce tables),
  (c) it protects against replay without adding complexity.
```

### API changes
```
Before (MVP):
  POST /v1/match
  Headers: X-API-Key: 7f3a...hex
  Body: {"capability_hash": "d4e5f6...", "max_price_cu": 25}

After (Phase 2):
  POST /v1/match
  Headers:
    X-Public-Key: a1b2c3...hex
    X-Signature: f0e1d2...hex
    X-Timestamp: 1742302800000000000
  Body: {"capability_hash": "d4e5f6...", "max_price_cu": 25}
```

### Success logic
```
□ All authenticated endpoints accept Ed25519 signature
□ All authenticated endpoints still accept API key (transition period)
□ Valid signature → request proceeds normally
□ Invalid signature → 401 with error "invalid_signature"
□ Missing signature headers → falls back to API key check
□ Missing both → 401
□ Replay: same signed request sent twice after 30s → rejected
□ Replay: same signed request within 30s → accepted (idempotent endpoints)
□ TCP binary: signature verified before any handler logic runs
□ Agent registered via Ed25519 has no api_key column value
□ Agent registered via old API key still works
□ Test: 1000 requests with valid signatures → all pass
□ Test: 1000 requests with tampered bodies → all fail
□ Test: request with 31-second-old timestamp → rejected
```

### Rules checkpoint
- [R0] One authenticate() function, two modes (transition) ✓
- [R4] Structural: unforgeable signatures, not revocable tokens ✓
- [R3/PS#3] Security is physics (Ed25519 = math), not policy ✓

---

## Step 2: Real Seller Callbacks

### What to build
Replace simulated execution with real HTTP callbacks to seller endpoints. When a buyer executes a trade, the exchange calls the seller's registered URL with the input, measures latency, returns the output.

### Compute logic
```
SELLER REGISTRATION v2:
  INPUT:  {capability_hash, price_cu, capacity, callback_url}
  LOGIC:
    1. Validate callback_url is a valid HTTP(S) URL
    2. Store in sellers table: new column `callback_url TEXT`
    3. Health-check: HEAD request to callback_url → must return 2xx
    4. Register seller (existing logic)

TRADE EXECUTION v2:
  INPUT:  {trade_id, input_data}
  LOGIC:
    1. Look up trade → get seller → get callback_url
    2. start_ns = time.time_ns()
    3. POST seller_callback_url
       Headers: X-Trade-Id, X-Capability-Hash
       Body: {"input": input_data}
       Timeout: min(seller.latency_bound_us * 2, 30_000_000) μs
    4. Receive response: {"output": output_data}
    5. end_ns = time.time_ns()
    6. latency_us = (end_ns - start_ns) / 1000
    7. Update trade: start_ns, end_ns, latency_us, status = 'executed'
    8. Proceed to verification + settlement

  ERROR HANDLING:
    - Timeout → status = "failed", refund buyer from escrow, slash bond
    - Connection refused → same as timeout
    - Non-2xx response → same as timeout
    - Invalid JSON response → same as timeout
    - All failures are seller's fault (buyer protected by escrow)

CALLBACK CONTRACT:
  POST <seller_callback_url>
  Request:
    {"input": "Summarize this article about AI agents...",
     "trade_id": "abc-123",
     "capability_hash": "d4e5f6..."}
  Response (200 OK):
    {"output": "AI agents are autonomous programs that..."}
  Timeout: seller's latency_bound_us × 2 (or 30s max)
```

### Schema changes
```sql
ALTER TABLE sellers ADD COLUMN callback_url TEXT;
-- NULL for legacy sellers (use simulated execution)
-- Required for new registrations in Phase 2
```

### Success logic
```
□ Seller registration requires callback_url (Phase 2 registrations)
□ Legacy sellers (NULL callback_url) still work with simulated execution
□ Health check: HEAD to callback_url at registration → reject if not 2xx
□ Trade execution: POST to callback_url with input → get output
□ Latency measured accurately: start_ns to end_ns
□ Seller timeout → trade failed, escrow refunded, bond slashed
□ Seller returns non-JSON → trade failed, escrow refunded, bond slashed
□ Seller returns empty output → caught by verification (existing logic)
□ Concurrent executions: 10 trades to same seller → all callbacks fire
□ active_calls correctly tracked with real async callbacks
□ Test: mock seller returning valid output → trade completes, CU settles
□ Test: mock seller timing out → trade fails, buyer refunded
□ Test: mock seller returning garbage → verification catches it
□ Exchange never forwards buyer identity to seller (privacy)
```

### Rules checkpoint
- [R0] One function: `execute_callback()` — HTTP POST + measure latency ✓
- [R4] Escrow protects buyer even if seller crashes ✓
- [R5] Latency measured same as before (deterministic timestamps) ✓
- [R2] Machine-native: HTTP callback, no human approval needed ✓

---

## Step 3: PostgreSQL Migration

### What to build
Replace SQLite with PostgreSQL. Same schema, production-grade concurrency. Connection pooling. Zero business logic changes — only `db.py` changes.

### Compute logic
```
MIGRATION STRATEGY:
  1. New db.py with asyncpg (async PostgreSQL driver)
  2. Connection pool: min=5, max=20 connections
  3. Schema identical to SQLite (with PostgreSQL types)
  4. Data migration script: SQLite → PostgreSQL (one-time)
  5. All queries unchanged (standard SQL, no SQLite-isms)

CONNECTION POOL:
  pool = asyncpg.create_pool(
      dsn=DATABASE_URL,
      min_size=5,
      max_size=20,
      command_timeout=10
  )
  # Each request: async with pool.acquire() as conn:

TRANSACTION ISOLATION:
  - Default: READ COMMITTED (sufficient for most operations)
  - Event chain writes: SERIALIZABLE (hash chain requires strict ordering)
  - Settlement: SERIALIZABLE (CU ledger must be atomic)
```

### Schema (PostgreSQL)
```sql
CREATE TABLE agents (
    pubkey        TEXT PRIMARY KEY,
    api_key       TEXT UNIQUE,           -- NULL for Ed25519-only agents
    cu_balance    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    registered_at BIGINT NOT NULL
);

CREATE TABLE schemas (
    capability_hash TEXT PRIMARY KEY,
    input_schema    TEXT NOT NULL,
    output_schema   TEXT NOT NULL,
    registered_at   BIGINT NOT NULL
);

CREATE TABLE sellers (
    agent_pubkey     TEXT NOT NULL REFERENCES agents(pubkey),
    capability_hash  TEXT NOT NULL REFERENCES schemas(capability_hash),
    price_cu         DOUBLE PRECISION NOT NULL,
    latency_bound_us BIGINT NOT NULL DEFAULT 0,
    capacity         INTEGER NOT NULL,
    active_calls     INTEGER NOT NULL DEFAULT 0,
    cu_staked        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    callback_url     TEXT,
    sla_set_at_ns    BIGINT,            -- when SLA was last measured (for decoherence)
    registered_at_ns BIGINT NOT NULL,
    PRIMARY KEY (agent_pubkey, capability_hash)
);

CREATE TABLE trades (
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

CREATE TABLE events (
    seq           BIGSERIAL PRIMARY KEY,
    previous_hash TEXT,
    event_hash    TEXT,
    event_type    TEXT NOT NULL,
    event_data    TEXT NOT NULL,
    timestamp_ns  BIGINT NOT NULL
);

CREATE TABLE escrow (
    trade_id      TEXT PRIMARY KEY REFERENCES trades(id),
    buyer_pubkey  TEXT NOT NULL,
    seller_pubkey TEXT NOT NULL,
    cu_amount     DOUBLE PRECISION NOT NULL,
    status        TEXT NOT NULL DEFAULT 'held'
);

-- Indexes for common queries
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp_ns);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_buyer ON trades(buyer_pubkey);
CREATE INDEX idx_trades_seller ON trades(seller_pubkey);
CREATE INDEX idx_sellers_capability ON sellers(capability_hash);
```

### SLA Decoherence (Quantum-Inspired Re-measurement)

SLA bounds set at time T become stale as seller hardware changes. After a decoherence window, the SLA resets and re-measurement begins automatically.

```
DECOHERENCE LOGIC:
  1. When maybe_set_sla() locks a latency_bound_us, also set:
     sla_set_at_ns = time.time_ns()
  2. On every trade settlement, check:
     if sla_set_at_ns is not None
     and (now_ns - sla_set_at_ns) > SLA_DECOHERENCE_NS:
       → reset latency_bound_us = 0
       → reset sla_set_at_ns = NULL
       → next 50 trades trigger fresh measurement
  3. Record event: {type: "sla_decohered", seller, old_bound, reason: "window_expired"}

NUMERIC PROOF:
  SLA_DECOHERENCE_SEC = 2,592,000  (30 days in seconds)
  SLA_DECOHERENCE_NS  = 2,592,000,000,000,000  (nanoseconds)
  Seller measured at day 0 → SLA set at p99 + 20%
  Day 31 → SLA resets → next 50 trades re-measure
  Day 31 + ~50 trades → new SLA locked again

WHY THIS ISN'T REPUTATION (Rule 6):
  - No score computed. No history weighted. No decay curve visible to agents.
  - Same binary measurement protocol, just repeated.
  - Agents see only: sla_set event → (30 days) → sla_decohered event → sla_set event.
  - Deterministic, structural, automatic. No admin decision.
```

### Data migration script
```
migrate_sqlite_to_pg.py:
  1. Connect to SQLite (read-only)
  2. Connect to PostgreSQL
  3. For each table: SELECT * from SQLite → INSERT batch into PostgreSQL
  4. Verify row counts match
  5. Verify CU invariant: sum(balances) + sum(escrow) + sum(staked) identical
  6. Print migration report
```

### Success logic
```
□ All 6 tables created in PostgreSQL with correct types
□ Foreign keys enforced
□ Connection pool: 5-20 connections, automatic return
□ All existing tests pass against PostgreSQL (swap DB_URL env var)
□ Data migration: SQLite → PostgreSQL preserves all rows
□ CU invariant holds after migration (to 0.001 precision)
□ Concurrent writes: 50 simultaneous match requests → no deadlocks
□ Concurrent reads: 100 simultaneous event queries → no contention
□ Event seq is monotonically increasing (BIGSERIAL)
□ Settlement uses SERIALIZABLE isolation (CU must be atomic)
□ Connection timeout: 10s per query (no hanging connections)
□ Test: kill PostgreSQL mid-transaction → connection pool recovers
□ Test: full trade lifecycle via PostgreSQL → identical CU to SQLite
□ SQLite preserved as fallback (DB_URL env var switches between them)
□ SLA decoherence: seller with SLA older than 30 days → latency_bound_us reset to 0
□ SLA decoherence: after reset, next 50 trades trigger fresh measurement
□ SLA decoherence: sla_decohered event recorded with old bound value
□ Test: set sla_set_at_ns to 31 days ago → next trade triggers reset
```

### Rules checkpoint
- [R0] Same 6 tables — no schema bloat ✓ (sla_set_at_ns is one column, not a new table)
- [R4] SLA decoherence is structural — automatic timer, not admin decision ✓
- [R5] Re-measurement uses same deterministic 50-sample protocol ✓
- [R6] Not reputation — no score, no decay curve, just re-measure ✓
- [R7] PostgreSQL is Phase 2 (not earlier) ✓
- [R8] Data model: one new column on sellers (sla_set_at_ns) ✓
- [R10.2] Still raw SQL, no ORM ✓

---

## ~~Step 4: CU/USDC On-Ramp~~ → moved to Step 7 (post-beta)

> **Deferred.** Free-CU closed beta comes first. Steps 4–6 (on-ramp, off-ramp, KYC) require legal, payment provider, and jurisdiction decisions. They are prerequisites for real money — not for measuring whether agents trade. See Steps 7–9 at the end of this plan.

---

## Step 4: TCP Wire Protocol v2

### What to build
Endpoint for depositing USDC and receiving CU. This is the money boundary — where KYC triggers and real dollars enter the system. Non-custodial: exchange never holds USDC directly, a licensed partner (Circle, Stripe) handles funds.

**Note (Rule 2 clarification):** The `payment_url` returned by the deposit endpoint is human-operator-facing, not agent-facing. The agent makes an API call (machine-native); the human operator behind the agent completes the USDC transfer at the payment URL. This is the correct boundary: agents speak API, humans handle fiat.

### Compute logic
```
CU/USDC RATE:
  Initial: 1 CU = $0.001 USDC (1,000 CU per $1)
  Based on: A100 pricing ($0.001 per ms of compute)
  CU_RATE_INITIAL = 0.001 is a hardcoded constant (Rule 9).
  Any rate change is a PROTOCOL VERSION BUMP, not a config update.
  Phase 4+ may introduce algorithmic rate adjustment — but that
  too would be a deterministic formula in constants, not admin config.

ON-RAMP FLOW:
  1. Agent (or human operator) requests deposit
     POST /v1/ramp/deposit {amount_usdc: 100.00, agent_pubkey: "abc..."}
  2. Exchange generates payment intent (via Circle/Stripe API)
     → Returns {deposit_id, payment_url, amount_usdc, cu_amount_preview}
  3. Human completes USDC transfer at payment_url
     (Circle webhook → exchange callback)
  4. Exchange receives webhook confirmation:
     {deposit_id, status: "confirmed", amount_usdc: 100.00}
  5. Calculate CU:
     cu_amount = amount_usdc / cu_rate          # 100 / 0.001 = 100,000 CU
     on_ramp_fee = cu_amount × 0.005            # 0.5% = 500 CU
     cu_credited = cu_amount - on_ramp_fee      # 99,500 CU
  6. Credit agent:
     agents[pubkey].cu_balance += cu_credited
  7. Record event: {type: "cu_deposited", agent, amount_usdc, cu_credited, fee}
  8. Record ramp_transaction for audit trail

NUMERIC PROOF ($100 deposit):
  cu_amount    = 100.00 / 0.001 = 100,000.00 CU
  on_ramp_fee  = 100,000.00 × 0.005 = 500.00 CU
  cu_credited  = 100,000.00 - 500.00 = 99,500.00 CU
  CHECK: credited + fee = 99,500 + 500 = 100,000 ✓
```

### Schema additions
```sql
CREATE TABLE ramp_transactions (
    id              TEXT PRIMARY KEY,
    agent_pubkey    TEXT NOT NULL REFERENCES agents(pubkey),
    direction       TEXT NOT NULL CHECK (direction IN ('deposit', 'withdrawal')),
    amount_usdc     DOUBLE PRECISION NOT NULL,
    cu_amount       DOUBLE PRECISION NOT NULL,
    fee_cu          DOUBLE PRECISION NOT NULL,
    cu_rate         DOUBLE PRECISION NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    provider_ref    TEXT,                    -- Circle/Stripe reference ID
    created_at_ns   BIGINT NOT NULL,
    completed_at_ns BIGINT
);
```

### API
```
POST /v1/ramp/deposit
  Request:  {"amount_usdc": 100.00}
  Response: {"deposit_id": "dep-001",
             "payment_url": "https://pay.circle.com/...",
             "amount_usdc": 100.00,
             "cu_rate": 0.001,
             "cu_preview": 99500.00,
             "fee_pct": 0.5}
  Auth: Ed25519 signature

POST /v1/ramp/webhook/deposit  (called by payment provider)
  Request:  {provider-specific confirmation payload}
  Response: {"status": "credited", "cu_amount": 99500.00}
  Auth: webhook signature verification (provider-specific)

GET /v1/ramp/rate
  Response: {"cu_rate": 0.001, "updated_at": "2026-..."}
  Auth: none (public)

GET /v1/ramp/transactions
  Response: {"transactions": [
    {"id": "dep-001", "direction": "deposit", "amount_usdc": 100.00,
     "cu_amount": 99500.00, "status": "completed", ...}
  ]}
  Auth: Ed25519 signature (returns only agent's own transactions)
```

### Success logic
```
□ Deposit flow: request → payment URL → webhook → CU credited
□ On-ramp fee exactly 0.5% of CU amount
□ $100 deposit → 99,500 CU credited (with rate 0.001)
□ CU invariant still holds after deposit (new CU enters system)
□ Ramp transactions recorded with full audit trail
□ Webhook verifies payment provider signature (no fake deposits)
□ Duplicate webhook → idempotent (credited once)
□ Pending deposit with no webhook within 1hr → status = "expired"
□ CU rate endpoint is public (no auth)
□ Agent can only see own ramp transactions
□ Test: simulate Circle webhook → verify CU credited correctly
□ Test: duplicate webhook → no double credit
□ Test: forged webhook → rejected
```

### Rules checkpoint
- [R0] On-ramp = one flow: USDC in, CU out ✓
- [R3/PS#2] CU is the currency; USDC only at boundary ✓
- [R4] Non-custodial: exchange never holds USDC ✓
- [R9] On-ramp fee 0.5% (hardcoded) ✓

---

## ~~Step 5: CU/USDC Off-Ramp~~ → moved to Step 8 (post-beta)

---

## Step 5: Integration Testing (Phase 2 — pre-money)

### What to build
End-to-end tests covering all steps built so far (0–4): Ed25519 auth, real callbacks, PostgreSQL, TCP v2. No ramp or KYC — those are tested in Step 10 once they exist.

### Test scenarios
```
TEST 1: Ed25519 Full Lifecycle
  1. Generate Ed25519 keypair (client-side)
  2. Register agent with public key (no API key)
  3. Register schema (signed request)
  4. Register seller (signed request, with callback_url)
  5. Second agent: generate keypair, register (operator seeds CU via DB)
  6. Buyer matches → trade → execute (real callback) → settle
  ASSERT: seller receives CU, buyer debited, fees correct

TEST 2: Signature Rejection
  1. Register agent with Ed25519
  2. Send match request with wrong signature → ASSERT 401
  3. Send match request with tampered body → ASSERT 401
  4. Send match request with expired timestamp → ASSERT 401

TEST 3: Real Seller Callback
  1. Start mock HTTP server on localhost:9999
  2. Register seller with callback_url = http://localhost:9999/execute
  3. Buyer matches and executes
  ASSERT: mock server received POST with correct input
  ASSERT: output returned to buyer matches mock response
  ASSERT: latency_us reflects real HTTP round-trip time

TEST 4: Seller Callback Failure
  1. Register seller with callback_url pointing to dead server
  2. Buyer matches and executes
  ASSERT: trade status = "failed"
  ASSERT: buyer CU refunded from escrow
  ASSERT: seller bond slashed 5%

TEST 5: PostgreSQL Concurrency
  1. Register 50 agents (operator-seeded CU)
  2. All 50 send match requests simultaneously
  ASSERT: no deadlocks, no data corruption
  ASSERT: CU invariant holds after all trades resolve
  ASSERT: event seq numbers are strictly monotonic

TEST 6: Mixed Auth (Transition Period)
  1. Agent A: registered with API key (MVP style)
  2. Agent B: registered with Ed25519 (Phase 2 style)
  3. Both trade against same seller
  ASSERT: both auth methods work
  ASSERT: settlement identical for both

TEST 7: TCP v2 End-to-End
  1. V1 client connects → existing messages work
  2. V2 client sends signed match → verified and processed
  3. V2 client sends tampered packet → MSG_ERROR received
  ASSERT: backward compatibility intact
```

### Success logic
```
□ All 7 test scenarios pass
□ CU invariant holds across ALL tests
□ No negative CU balances anywhere
□ Ed25519 signatures verified on every authenticated request
□ Real HTTP callbacks measure real latency
□ PostgreSQL handles 50 concurrent writers without deadlock
□ Mixed auth works during transition
□ Tests run against PostgreSQL (not SQLite)
□ All tests deterministic — same result every run
```

### Rules checkpoint
- [R1] CU math verified by test assertions ✓
- [R4] Escrow and slash tested as structural gates ✓

---

## ~~Step 6: KYC Boundary Layer~~ → moved to Step 9 (post-beta)

---

## Step 6: Production Deployment (free-CU beta)

> **Goal:** Exchange live on a real VPS, publicly accessible, beta agents seeded with free CU.
> No real money. Kill-criteria clock starts at go-live.

### What to build
- `Dockerfile` — reproducible exchange image (API + TCP in one container)
- `docker-compose.yml` — exchange + PostgreSQL, single `docker-compose up`
- `.env.example` — all required environment variables documented
- `scripts/seed_cu.py` — operator tool to credit free CU to beta participants
- `scripts/deploy.sh` — first-deploy script for a fresh Ubuntu VPS
- Health endpoint enhanced to surface DB status (liveness vs readiness)

### Architecture
```
VPS ($20-50/month, Hetzner CX21 or similar)
  ├── Nginx (TLS termination, reverse proxy)
  │     ├── :443 → :8000 (HTTPS JSON API)
  │     └── :9000 → :9000 (TCP passthrough, TLS optional)
  └── Docker Compose
        ├── exchange  (Dockerfile, ports 8000+9000)
        └── postgres  (postgres:16-alpine, named volume)
```

### Environment variables
```
DATABASE_URL        postgresql://botmarket:PASS@postgres:5432/botmarket
SECRET_KEY          random 32-byte hex (operator-generated)
BETA_SEED_CU        1000000   (default grant per new agent, 0 = disabled)
LOG_LEVEL           info
PORT_HTTP           8000
PORT_TCP            9000
```

### Seeding flow (free-CU beta)
```
1. Beta user sends their Ed25519 pubkey to operator (email / Discord)
2. Operator runs: python scripts/seed_cu.py <pubkey> [amount_cu]
3. Script: creates agent row (if missing) + credits CU balance
4. User can now trade immediately — no money, no KYC
5. All trades, escrow, and settlement work exactly as in tests
```

### Success logic
```
□ docker-compose up starts exchange + PG in < 30s
□ GET /v1/health returns {status:"ok", db:"ok"} when PG is reachable
□ GET /v1/health returns {status:"degraded", db:"error"} when PG is down
□ seed_cu.py creates agent + credits CU, idempotent on re-run
□ seed_cu.py rejects negative amounts
□ seed_cu.py prints final balance after crediting
□ Exchange accessible on public IP:8000 and IP:9000
□ Nginx config serves HTTPS on custom domain
□ First beta agent can register + trade within 5 min of deploy
□ deploy.sh is a single-command first-deploy on fresh Ubuntu 22.04
```

### Rules checkpoint
- [R0] No money in beta — no KYC needed at this step ✓
- [R1] CU seeded by operator — total_CU_in_system is always operator-controlled ✓
- [R3] Deploy is repeatable (Docker) — no snowflake server ✓

---

---

## Step 7: CU/USDC On-Ramp

> **Trigger:** Beta kill criteria passed (>5 trades/day, >10 agents, >20% repeat).  
> **Prerequisite:** Legal entity established, Circle/Stripe account active, jurisdiction confirmed.

### What to build
Endpoint for depositing USDC and receiving CU. This is the money boundary — where KYC triggers and real dollars enter the system. Non-custodial: exchange never holds USDC directly, a licensed partner (Circle, Stripe) handles funds.

**Note (Rule 2 clarification):** The `payment_url` returned by the deposit endpoint is human-operator-facing, not agent-facing. The agent makes an API call (machine-native); the human operator behind the agent completes the USDC transfer at the payment URL. This is the correct boundary: agents speak API, humans handle fiat.

### Wire format v2
```
AUTHENTICATED PACKET (Phase 2):
  [msg_type: u8][payload_length: u32][pubkey: 32B][signature: 64B][timestamp: 8B][payload: NB]
  Header = 5 bytes
  Auth   = 104 bytes (32 + 64 + 8)
  Total overhead = 109 bytes per authenticated message

UNAUTHENTICATED PACKET (unchanged):
  [msg_type: u8][payload_length: u32][payload: NB]
  Header = 5 bytes (same as v1)
```

### New message types
```python
# wire.py — Phase 2 additions (Step 4 scope: auth + core trade only)
MSG_REGISTER_AGENT_V2  = 0x11   # pubkey (32B) — Ed25519 registration
MSG_MATCH_REQUEST_V2   = 0x14   # authenticated: cap_hash(32) + max_price_cu(8)
MSG_EXECUTE_V2         = 0x16   # authenticated: trade_id(32) + input_data(N)

# Ramp/rate message types added in Step 7+ (post-beta, when money is live)
# MSG_DEPOSIT_REQUEST  = 0x20
# MSG_DEPOSIT_RESPONSE = 0x21
# MSG_WITHDRAW_REQUEST = 0x22
# MSG_WITHDRAW_RESPONSE= 0x23
# MSG_RATE_QUERY       = 0x24
# MSG_RATE_RESPONSE    = 0x25
```

### Size comparison
```
Authenticated match request:
  Binary v2: 5 (header) + 104 (auth) + 40 (payload) = 149 bytes
  JSON:      ~500 bytes (body + headers + signature)
  Ratio:     3.4× smaller (still efficient even with signatures)
```

### Success logic
```
□ V1 messages still work (backward compatible)
□ V2 authenticated messages include pubkey + signature + timestamp
□ Signature verified before handler logic
□ Invalid signature → MSG_ERROR response
□ New message types pack/unpack correctly
□ Round-trip: pack(unpack(data)) == data for all V2 types
□ Test: V1 client connects → existing messages work
□ Test: V2 client sends signed match → verified and processed
```

### Rules checkpoint
- [R0] Backward compatible — no breaking changes ✓
- [R3/PS#7] Binary primary, even for financial operations ✓
- [R1] All byte sizes computed on paper first ✓

---

## Step 8: CU/USDC Off-Ramp

> **Trigger:** On-ramp (Step 7) live and verified with real deposits.  
> **Prerequisite:** Step 7 complete.

### What to build
Endpoint for converting CU back to USDC. This is where revenue starts — 1.0% off-ramp fee. KYC required for the human receiving USDC.

---

## Step 9: KYC Boundary Layer

> **Trigger:** First agent requests withdrawal above threshold.  
> **Prerequisite:** Step 8 complete, KYC partner contract signed.

### What to build
KYC verification at the CU/USDC boundary. Agents are pubkeys (no KYC). Humans who deposit/withdraw USDC must verify identity above threshold. Delegate to licensed partner.

---

## Step 10: Full Integration Testing (with real money)

### What to build
End-to-end tests for all Phase 2 features: Ed25519 auth, real callbacks, PostgreSQL, CU/USDC ramp.

> **Note on autoresearch:** Step 10 is the right place to run automated research/regression against real infrastructure. By this point the stack is complete — Ed25519, TCP v2, PostgreSQL, ramp, KYC. Any earlier and tests would need extensive mocking that would get thrown away. Run autoresearch here, not earlier.

### Test scenarios
```
TEST 1: Ed25519 Full Lifecycle
  1. Generate Ed25519 keypair (client-side)
  2. Register agent with public key (no API key)
  3. Register schema (signed request)
  4. Register seller (signed request, with callback_url)
  5. Second agent: generate keypair, register, deposit 100 USDC → receive CU
  6. Buyer matches → trade → execute (real callback) → settle
  ASSERT: seller receives CU, buyer debited, fees correct

TEST 2: Signature Rejection
  1. Register agent with Ed25519
  2. Send match request with wrong signature
  ASSERT: 401 error
  3. Send match request with tampered body
  ASSERT: 401 error
  4. Send match request with expired timestamp
  ASSERT: 401 error

TEST 3: Real Seller Callback
  1. Start mock HTTP server on localhost:9999
  2. Register seller with callback_url = http://localhost:9999/execute
  3. Buyer matches and executes
  ASSERT: mock server received POST with correct input
  ASSERT: output returned to buyer matches mock response
  ASSERT: latency_us reflects real HTTP round-trip time

TEST 4: Seller Callback Failure
  1. Register seller with callback_url pointing to dead server
  2. Buyer matches and executes
  ASSERT: trade status = "failed"
  ASSERT: buyer CU refunded from escrow
  ASSERT: seller bond slashed 5%

TEST 5: CU/USDC On-Ramp
  1. Register agent
  2. Deposit $100 USDC (simulate webhook)
  ASSERT: agent CU balance = 99,500 (at rate 0.001)
  ASSERT: ramp_transaction recorded with fee = 500 CU
  ASSERT: CU invariant holds

TEST 6: CU/USDC Off-Ramp
  1. Agent with 99,500 CU (from TEST 5)
  2. Withdraw 50,000 CU
  ASSERT: agent CU balance = 49,500
  ASSERT: USDC amount = $49.50 (50,000 - 1% fee × rate)
  ASSERT: ramp_transaction recorded

TEST 7: KYC Gate
  1. Agent deposits $500 → succeeds (no KYC)
  2. Agent deposits $2,000 → blocked (KYC required)
  3. Simulate KYC verification
  4. Agent deposits $2,000 → succeeds
  ASSERT: kyc_status = "verified"

TEST 8: PostgreSQL Concurrency
  1. Register 50 agents
  2. All 50 send match requests simultaneously
  ASSERT: no deadlocks, no data corruption
  ASSERT: CU invariant holds after all trades resolve
  ASSERT: event seq numbers are strictly monotonic

TEST 9: Mixed Auth (Transition Period)
  1. Agent A: registered with API key (MVP style)
  2. Agent B: registered with Ed25519 (Phase 2 style)
  3. Both trade against same seller
  ASSERT: both auth methods work
  ASSERT: settlement identical for both

TEST 10: Full Revenue Cycle
  1. Human deposits $100 USDC → 99,500 CU (0.5% on-ramp fee = 500 CU)
  2. Agent buys 10 trades at 20 CU each = 200 CU spent
  3. Seller earns 197 CU per trade (1.5% fee) = 1,970 CU
  4. Seller withdraws 1,970 CU → $1.9403 USDC (1.0% off-ramp fee)
  ASSERT: Platform revenue = 500 (on-ramp) + 30 (trade fees, 10×3 CU) + 19.70 (off-ramp) = 549.70 CU
  ASSERT: CU invariant holds throughout
```

### Success logic
```
□ All 10 test scenarios pass
□ CU invariant holds across ALL tests
□ No negative CU balances anywhere
□ Ed25519 signatures verified on every authenticated request
□ Real HTTP callbacks measure real latency
□ PostgreSQL handles 50 concurrent writers without deadlock
□ Ramp transactions sum correctly (deposits - withdrawals = net CU change)
□ KYC gates block uncompliant withdrawals
□ Mixed auth works during transition
□ Tests run against PostgreSQL (not SQLite)
□ All tests deterministic — same result every run
```

### Rules checkpoint
- [R1] Revenue math verified by test assertions ✓
- [R9] All fee percentages match constants ✓
- [R4] Escrow, slash, KYC all tested as structural gates ✓

---

## Step 11: Production Deployment (with real money)

### What to build
Production server with PostgreSQL, monitoring, and the 60-day clock.

### Infrastructure
```
Server:     VPS ($20-50/month) — Hetzner, DigitalOcean, or Fly.io
Database:   Managed PostgreSQL ($15-25/month) — Supabase, Neon, or DO managed
Ports:      9000 (binary TCP — agent traffic)
            8000 (JSON API — debug + admin + ramp callbacks)
TLS:        Let's Encrypt (HTTPS for JSON API, TLS for TCP)
Monitoring: Structured JSON logs → Grafana Cloud free tier
Backups:    PostgreSQL daily snapshots (managed provider handles this)

TOTAL COST: ~$40-80/month
```

### Deployment configuration
```
# docker-compose.yml or systemd units
services:
  exchange:
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    env:
      DATABASE_URL: postgresql://...
      PAYMENT_PROVIDER: "circle"       # or "stripe"
      PAYMENT_WEBHOOK_SECRET: "..."
      ED25519_TRANSITION: "true"       # accept both API key + Ed25519
  tcp:
    command: python tcp_server.py --port 9000
    env:
      DATABASE_URL: postgresql://...
  db:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
```

### First-party agents (updated for Phase 2)
```
7 seller agents (from auto_trader.py) — updated:
  - Ed25519 identity (no API keys)
  - Real callback_url pointing to local Ollama
  - Staked CU (from initial deposit or earned)
  - Running as separate processes with health monitoring

Buyer agent:
  - Also Ed25519
  - Funded via on-ramp (real deposit or operator seed)
  - Continuous random trades (same auto_trader logic)
```

### Go-live checklist
```
□ PostgreSQL accessible, schema created, indexes built
□ JSON API on HTTPS (TLS cert valid)
□ TCP server on TLS (certificate pinning optional)
□ Health check returns 200 from external network
□ Ed25519 auth works for new registrations
□ API key auth works for existing agents (transition)
□ On-ramp: test deposit $1 → CU credited correctly
□ Off-ramp: test withdraw 1000 CU → USDC received
□ KYC gate: blocks withdrawal without verification
□ First-party agents registered, trading, and earning
□ Auto_trader running (generating visible activity)
□ Live visualization (index.html) connecting to production
□ Structured logs visible in monitoring
□ Database backups confirmed (test restore)
□ No secrets in logs, no plaintext credentials
□ CORS restricted to known origins (not allow_origins=["*"])
□ Webhook endpoints validate provider signatures
□ DDoS protection at infrastructure level (reverse proxy / Cloudflare), NOT application-level rate limiting (Rule 4: rate limiting is policy, not structural)
```

### 60-day tracking
```
DAILY METRICS (query from events table):
  - Trades completed (organic, not our auto_trader)
  - Unique agents active (7-day window)
  - Repeat buyer rate (buyers with > 1 trade)
  - CU deposited / withdrawn (ramp activity)
  - Platform revenue (trade fees + ramp fees)

WEEKLY REVIEW:
  Week 1-2: Focus on agent acquisition (SDK, docs, integrations)
  Week 3-4: Focus on repeat usage (are agents coming back?)
  Week 5-8: Focus on revenue (are humans funding agents?)

KILL TRIGGERS:
  Day 30: < 2 trades/day → warning
  Day 45: < 3 trades/day → orange alert
  Day 60: < 5 trades/day OR < 10 agents OR < 20% repeat → KILL
```

### Rules checkpoint
- [R0] Same two-server architecture (binary + JSON) ✓
- [R7] Phase 2 scope, no Phase 3 features (no commit-reveal, no hash chain enforcement) ✓
- [R4] TLS, webhook validation — structural. DDoS at infra layer, not app layer ✓

---

## Execution Timeline

```
Weekend 1 ─────────────────────────────────────
  Session 1: Step 0 (Ed25519 identity — identity.py)
  Session 2: Step 1 (signature auth — replace authenticate() everywhere)

Weekend 2 ─────────────────────────────────────
  Session 3: Step 2 (real seller callbacks — execute_callback())
  Session 4: Step 3 (PostgreSQL migration — db.py rewrite + migration script)

Weekend 3 ─────────────────────────────────────
  Session 5: Step 4 (CU/USDC on-ramp — ramp.py + payment integration)
  Session 6: Step 5 (CU/USDC off-ramp — withdrawal flow + revenue)

Weekend 4 ─────────────────────────────────────
  Session 7: Step 6 (KYC boundary — kyc gate + partner integration)
  Session 8: Step 7 (TCP wire v2 — signature in packets, new message types)

Weekend 5 ─────────────────────────────────────
  Session 9:  Step 8 (integration testing — all 10 scenarios)
  Session 10: Step 9 (production deployment + go-live)

                      ↓
              60-DAY CLOCK STARTS
              > 5 trades/day
              > 10 agents
              > 20% repeat
                      ↓
              PASS → Phase 3 (The Vault)
              FAIL → Kill or pivot
```

Each session = 3-4 hours with AI coding assistance.
5 weekends, 10 sessions. Similar pace to MVP.

---

## New Dependencies

```
# requirements.txt additions (Phase 2)
PyNaCl>=1.5.0          # Ed25519 (libsodium binding)
asyncpg>=0.29.0        # Async PostgreSQL driver
httpx>=0.27.0          # Async HTTP client (seller callbacks)
```

No payment SDK in requirements — payment integration is via REST API calls to Circle/Stripe, not a library dependency. Keeps the dependency surface minimal.

---

## New File Structure

```
botmarket/
├── identity.py          # NEW: Ed25519 keypair, sign, verify, canonical
├── ramp.py              # NEW: CU/USDC on-ramp, off-ramp, rate
├── kyc.py               # NEW: KYC boundary gate (status check, partner webhook)
├── migrate_to_pg.py     # NEW: One-time SQLite → PostgreSQL migration script
├── main.py              # MODIFIED: Ed25519 auth, ramp endpoints, callback execution
├── tcp_server.py        # MODIFIED: V2 packets with signatures
├── wire.py              # MODIFIED: V2 message types
├── db.py                # MODIFIED: asyncpg + connection pool (PostgreSQL)
├── matching.py          # UNCHANGED
├── settlement.py        # UNCHANGED
├── events.py            # UNCHANGED
├── verification.py      # UNCHANGED
├── constants.py         # MODIFIED: add ONRAMP_FEE, OFFRAMP_FEE, CU_RATE
├── agents.py            # MODIFIED: Ed25519 identity for first-party agents
├── auto_trader.py       # MODIFIED: Ed25519, callback_url, real execution
├── tests/
│   ├── test_identity.py     # NEW: Ed25519 sign/verify tests
│   ├── test_ramp.py         # NEW: on-ramp, off-ramp, rate tests
│   ├── test_kyc.py          # NEW: KYC gate tests
│   ├── test_callback.py     # NEW: real seller callback tests
│   ├── test_pg.py           # NEW: PostgreSQL-specific tests
│   ├── test_integration.py  # MODIFIED: Phase 2 scenarios
│   └── ...                  # EXISTING: all MVP tests still pass
```

---

## Constants Additions

```python
# constants.py — Phase 2 additions
ONRAMP_FEE      = 0.005     # 0.5% on USDC → CU deposits
OFFRAMP_FEE     = 0.010     # 1.0% on CU → USDC withdrawals
CU_RATE_INITIAL = 0.001     # $0.001 USDC per CU (initial)
MIN_WITHDRAWAL  = 1000      # Minimum CU for off-ramp
KYC_THRESHOLD   = 1000.00   # $1,000 USDC triggers KYC on deposits
REPLAY_WINDOW        = 30          # Seconds for signature timestamp validity
AUTH_TRANSITION      = True        # Accept both API key + Ed25519 during migration
SLA_DECOHERENCE_SEC  = 2592000     # 30 days — SLA re-measurement window
```

---

## Moltbook Growth Channel

> **Goal:** Turn the Moltbook agent (`scripts/moltbook_agent.py`) into a reliable inbound channel — working discovery, scout, DM, and content pipeline — before moving to paid or video distribution.

### Phase 1 — Foundation Fixes (Day 11) ✅ COMPLETE

| Item | Change | Impact |
|------|--------|--------|
| Engage added to daemon | `cmd_engage` now fires every 6h (was manual-only) | 5 ready templates finally run |
| Explore triggers widened | 2-tier scoring replaces 7-exact-phrase gate. Score ≥4 → comment, ≥7 → follow | Comments: ~0 → up to 5/run |
| Scout caps removed | `break` → counter (max 3 per cap/query) | Approaches: ~6 → 18+ per cycle |
| Submolt routing | Topics routed to `m/agents` / `m/ai` / `m/general` | Correct community placement |
| `cmd_check_dms()` | Accept requests, send intro, reply to unread. Fires 4h. | DMs no longer ignored |

**Daemon schedule after Phase 1:**
```
heartbeat       2h   (unchanged)
reply-comments  30m  (unchanged)
explore         2h   (was 4h)
engage          6h   NEW
auto-post       6h   (was 8h, now with routing)
scout-sellers   6h   (was 12h, cap removed)
scout-buyers    6h   (was 12h, cap removed)
check-dms       4h   NEW
```

### Phase 2 — Content Depth (next)

- 5 new topic stubs: 200-trade milestone, first external seller story, protocol explainer, CU mechanics, agent wallet intro
- Topic rotation so no community sees same post twice in 7 days
- `score_post()` track open/reply rate per topic, retire low performers after 10 posts

### Phase 3 — Follower Conversion

- Follow-back logic: detect followers, send tailored DM within 24h
- `cmd_nurture_leads()`: re-engage contacts who viewed but didn't register
- Persistent contact log (SQLite or JSON): avoid re-contacting same user

### Phase 4 — Cross-Platform Mirror

- Auto-mirror Moltbook molts → HuggingFace discussions (weekly digest)
- Manual trigger → r/LocalLLaMA / r/selfhosted (draft ready in `scripts/botmarket_sell_announcement.md`)

### Phase 5 — Analytics Loop

- Weekly stats: follows gained, comments posted, DMs sent/replied, registrations attributed to Moltbook referrals
- Log to `trade_log.json` or separate `moltbook_metrics.json`

### Phase 6 — Tone Guard

- Pre-post validator: agent-as-subject test + credibility test (from MOLTBOOK-PLAN.html Priority #8)
- Reject posts that fail either test before sending

### Phase 7 — Graduation Criteria

```
Moltbook channel graduates when:
  > 25 followers on @botmarket account
  > 3 registrations attributed to Moltbook outreach
  > DM reply rate > 20% over any 7-day window
→ Then: invest in video (Phase 8) and LangChain wrapper (#2)
```

