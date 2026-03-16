# Dimension 12: MVP Definition

## MVP Philosophy

The autoresearch principle: **constrain scope ruthlessly**. The MVP must answer exactly ONE question:

> **"Will AI agents trade services through an exchange mechanism?"**

If yes → iterate and expand.
If no → pivot or kill.

## What the MVP IS

```
A working exchange where:
1. An agent can register as a seller (list a capability + price)
2. Another agent can request that capability (match request)
3. The exchange matches the request to the best seller
4. The service is executed
5. Payment is settled
```

That's it. Everything else is noise at this stage.

## What the MVP is NOT

```
❌ A token/cryptocurrency
❌ A blockchain/Solana integration (USDC settlement later)
❌ A match engine handling 1M requests/sec
❌ A beautiful web UI
❌ A mobile app
❌ A comprehensive API marketplace
❌ A reputation system
❌ A dispute resolution platform
❌ A governance system
❌ Multi-region infrastructure
❌ An order book (no bids resting, no market depth)
```

## MVP Architecture

```
┌───────────────────────────────────┐
│  JSON Sidecar (FastAPI)           │
│  (Developer debugging only)       │
│                                   │
│  POST /v1/agents/register         │
│  POST /v1/sellers/register        │
│  POST /v1/match                   │
│  GET  /v1/sellers/:hash           │
│  POST /v1/trades/:id/execute      │
│  GET  /v1/events/:pubkey          │
│                                   │
├───────────────────────────────────┤
│  Match Engine (Python)             │
│  (Best seller by price+latency)   │
├───────────────────────────────────┤
│  Seller Table + Event Log          │
│  (capability_hash → sellers,      │
│   raw trade events)               │
├───────────────────────────────────┤
│  SQLite                            │
│  (Agents, sellers, trades, CU     │
│   balances, raw events)           │
├───────────────────────────────────┤
│  Settlement: CU Ledger             │
│  (Debit buyer CU, credit seller)  │
│  (Off-ramp deferred to Phase 2)   │
└───────────────────────────────────┘

Phase 2 upgrade path (when thesis validated):
  SQLite → PostgreSQL
  API key → Ed25519
  JSON sidecar → Binary TCP core (agents connect directly)
  Python/FastAPI → Rust match engine
  Single VPS → Fly.io multi-region
```

### Tech Stack (MVP)
```
Language:    Python (accessible to non-developers, AI-assistable, vast ecosystem)
Framework:   FastAPI (simple, well-documented, async support)
Database:    SQLite (zero config, single file, good enough for validation)
Match:       In-memory seller tables (dict[str, list] keyed by capability hash)
Protocol:    JSON sidecar for debugging (binary TCP core is Phase 2)
Auth:        API key (Ed25519 cryptographic identity is Phase 2)
Deploy:      Local / single VPS ($5/month), $5-20/month
Currency:    Compute Units (CU) — 1 CU = 1ms GPU compute (concrete definition)
```

### Why Rescoped from Original Spec?
```
Original:  TypeScript + Hono + Bun + PostgreSQL + Drizzle + Binary TCP + Ed25519
Rescoped:  Python + FastAPI + SQLite + JSON sidecar + API key

Reason:    Founder is a hobby AI user, not a developer/programmer.
           Original 22-day estimate assumed experienced TypeScript developer.
           Binary TCP, Ed25519, and PostgreSQL are deep engineering territory.
           AI coding assistants can write the code, but debugging, deploying,
           and maintaining production infra requires engineering experience.

What stays (the thesis validation):
  ✓ Schema-hash capability discovery (SHA-256 — 3 lines of Python)
  ✓ Match engine concept (find best seller for a request)
  ✓ CU ledger (simple balance tracking)
  ✓ 1.5% fee deduction
  ✓ Raw event log (every trade is a fact, not a stat)
  ✓ Single 5% bond slash on any violation

What's deferred (engineering moat, not thesis validation):
  ✗ Binary TCP protocol → JSON sidecar (binary is optimization, not validation)
  ✗ Ed25519 crypto auth → API key (crypto identity is moat, not MVP)
  ✗ PostgreSQL → SQLite (no config, good enough for <1000 agents)
  ✗ Discovery by example → exact hash match only (add when fragmentation >30%)
  ✗ Off-ramp (CU→USDC) → earn-only MVP

What this still proves to investors:
  The same thing — agents can discover each other by capability hash
  and get matched through a match engine. The binary protocol
  and crypto identity are things you DESCRIBE to investors, not demo.
```

## MVP Features (Ranked by Priority)

### Must Have (Weekends 1-8, ~2-4 weekends with AI assistance)
| Feature | Details | Effort |
|---------|---------|--------|
| Agent registration | API key generation, register agent | 1 session |
| Schema store | Content-addressed schema store (capability hashes) | 1 session |
| Seller registration | Register as seller with price + capability hash | 1 session |
| Match engine | Find best seller for a match request (price, then latency) | 1-2 sessions |
| Trade execution | Connect matched buyer/seller, proxy JSON data | 1-2 sessions |
| CU Ledger | SQLite balance table (deposit CU, settle trades) | 1 session |
| Event log | Record raw trade facts (no aggregated stats) | 1 session |
| JSON sidecar | FastAPI endpoints for all operations (debugging interface) | included above |

**Total: ~8-14 sessions (2-4 weekends with AI coding assistance)**

Note: "session" = 3-4 hours of focused work with AI assistant. Previous estimate of
"22 dev-days (5 weeks solo)" assumed an experienced TypeScript developer building
binary TCP + PostgreSQL + Ed25519. This rescoped version is achievable for a
non-developer with AI assistance.

### Should Have (Week 5-8)
| Feature | Details | Effort |
|---------|---------|--------|
| Binary TCP core | Binary protocol for agent connections (not JSON) | 3 days |
| Discovery by example | Send example I/O bytes, find matching schemas | 2 days |
| Bond enforcement | Auto-slash 5% bond on any violation | 1 day |
| Auto-derived SLA | Measure first 50 calls, set latency_bound automatically | 1 day |
| Python SDK | `pip install botmarket` — 50-line client | 2 days |
| Event query API | `/v1/events/{pubkey}` returns raw trade facts | 1 day |

### Nice to Have (Week 9-12)
| Feature | Details | Effort |
|---------|---------|--------|
| MCP bridge | BOTmarket as MCP tool server (sidecar process) | 3 days |
| Ed25519 auth | Replace API keys with cryptographic identity | 2 days |
| CLI tool | `botmarket list`, `botmarket match` (developer convenience) | 2 days |
| Hash chain | Tamper-evident event log (structural security) | 3 days |

## MVP Success Metrics

### Primary Metric (The ONE Number)
```
Daily Matched Trades
```

This is the single metric that tells us if the exchange is working. Not signups, not listed agents, not page views — **matched trades**.

### Target: 10 organic trades/day within 30 days of launch

If we hit 10 daily organic trades (not our own test agents), the thesis is validated.

### Supporting Metrics
| Metric | Target (30 days) | Why it matters |
|--------|-----------------|----------------|
| Registered agents | 50 | Supply side health |
| Active agents (traded in 7d) | 20 | Engagement |
| Listed services (unique types) | 10 | Catalog breadth |
| Avg trade value | > 1 CU | Real economic activity |
| Match rate | > 50% | Order book liquidity |
| Avg time to match | < 60s | Exchange utility |
| Trade completion rate | > 90% | Service reliability |
| Repeat buyers | > 30% | Value being delivered |

### Kill Criteria
```
STOP if after 60 days:
  - < 5 organic trades/day
  - < 10 active agents
  - < 20% repeat usage
  - Qualitative feedback: "I'd rather just call the API directly"

PIVOT if:
  - Agents trade but match engine is unnecessary → maybe simple directory
  - Only humans use it, not agents → pivot to API marketplace
  - Only one service type is popular → niche down to that vertical
```

## MVP Demo Scenario

### The "Hello World" of BOTmarket

```
# Agent A: Summarization service
# Registers on exchange, lists as seller

# Agent A registers:
$ curl -X POST https://api.botmarket.exchange/v1/agents/register \
  -d '{"pubkey": "ed25519:7xKX..."}'
→ {"agent_id": "7xKX...", "cu_balance": 0}

# Agent A registers its capability schema:
#   input:  { type: "text", encoding: "utf8", max_bytes: 100000 }
#   output: { type: "text", encoding: "utf8", max_bytes: 5000 }
#   capability_hash = SHA-256(input_schema || output_schema) = 0xd4e5...

# Agent A registers as seller: "I offer 0xd4e5... for 20 CU per call"
$ curl -X POST https://api.botmarket.exchange/v1/sellers/register \
  -d '{"capability_hash": "0xd4e5...", "price_cu": 20, "capacity": 100}'
→ {"status": "registered", "capability_hash": "0xd4e5...", "price_cu": 20}

# Agent B needs capability 0xd4e5...
# Sends a match request (NOT an order — no resting, no bid)
$ curl -X POST https://api.botmarket.exchange/v1/match \
  -d '{"capability_hash": "0xd4e5...", "max_price_cu": 25}'
→ {"trade_id": "trade_001", "seller": "7xKX...", "price_cu": 20, "status": "matched"}

# Execute: Agent B sends input, Agent A returns output
$ curl -X POST https://api.botmarket.exchange/v1/trades/trade_001/execute \
  -d '{"input": "Long article about AI agent commerce..."}'
→ {"output": "AI agents are forming autonomous markets...", "latency_ms": 145}

# Settlement: 20 CU transferred from B to A (minus 1.5% fee = 0.3 CU)
# Agent A receives: 19.7 CU
# Raw event recorded: "agent_B ← agent_A, 0xd4e5..., 20 CU, 145ms, pass"

# All via JSON sidecar for demo.
# In production, agents connect via binary TCP — zero JSON overhead.
```

## Implementation Plan

### Rescoped for Non-Developer with AI Assistance

```
Original plan: 22 dev-days, TypeScript + PostgreSQL + Binary TCP + Ed25519
Rescoped plan: 8-14 sessions (2-4 weekends), Python + SQLite + JSON sidecar + API key

The match engine model (request → match → execute → settle) is SIMPLER
to build than a CLOB order book. No order management, no partial fills,
no resting orders. Just a seller table and a match function.
```

### Weekend 1: Foundation
```
Session 1: Project setup
  - Python + FastAPI + SQLite
  - Virtual environment + requirements.txt
  - Basic health check endpoint

Session 2: Agent Registry + Schema Store
  - API key-based registration
  - Content-addressed schema store (I/O schema → SHA-256 capability hash)
  - Agent CRUD endpoints (JSON sidecar)
```

### Weekend 2: Exchange Core
```
Session 3: Seller Table + Match Engine
  - In-memory seller tables keyed by capability hash
  - Seller registration endpoint (price, capacity, capability hash)
  - Match request endpoint (find best seller by price, then latency)

Session 4: Trade Execution
  - Connect matched buyer/seller via JSON payloads
  - Schema verification (output matches declared schema)
  - Latency measurement
```

### Weekend 3: Settlement & Events
```
Session 5: CU Ledger System
  - CU balance per agent (SQLite table)
  - Debit buyer CU, credit seller CU on completion
  - Fee deduction (1.5% in CU)
  - Bond slash (5% on any violation)

Session 6: Event Log
  - Record raw trade facts (not aggregated stats)
  - Event query endpoint (by seller pubkey, by capability hash)
  - Auto-derive SLA from first 50 responses
```

### Weekend 4: Test & Deploy
```
Session 7: Testing
  - Integration tests for full trade lifecycle
  - 2-3 test agents exercising the exchange
  - Edge cases (no match found, schema mismatches, bond slashing)

Session 8: Deployment
  - Deploy to single VPS or Fly.io
  - Basic monitoring (health check, error logging)
  - API documentation + quick start guide
```

### Full-Spec Reference Plan (For Experienced Developer, When Available)
```
The Rust + PostgreSQL + Binary TCP + Ed25519 plan
is the Phase 2 engineering upgrade path when the thesis is
validated with the Python MVP.

Week 1: Rust match engine + binary TCP server + PostgreSQL
Week 2: Ed25519 auth + hash chain + commit-reveal
Week 3: Bond enforcement + auto-SLA + discovery by example
Week 4-5: Python SDK + testing + deployment
```

## Post-MVP Roadmap

```
MVP validates → then:

Month 2-3: Binary TCP core, discovery by example, Python SDK (50-line client)
Month 3-4: Ed25519 auth, hash chain, commit-reveal (structural security)
Month 4-6: CU/USDC off-ramp (Phase 2)
Month 6-9: Rust match engine rewrite, horizontal scaling
```

## Score: 9/10

**Completeness:** Clear MVP with CU currency (concrete definition), schema-hash addressing, match engine (not order book), JSON sidecar, raw event log, deterministic verification.
**Actionability:** Rescoped stack (Python/FastAPI/SQLite) is buildable by a non-developer with AI assistance. 2-4 weekends timeline is honest. Match engine is simpler to build than CLOB — fewer data structures, no order management.
**Gap:** Need to prototype match engine and schema-hash matching with real agents. Full-spec plan preserved for Phase 2 when engineering talent joins.
**Paradigm shifts applied:** #4 (Match Don't Trade — seller table + match request), #5 (CU = Measurement — 1ms GPU), #7 (Binary-Only Core — JSON as sidecar), #8 (Facts Not Stats — raw event log). Simplifications: no barter, no off-ramp in MVP, single 5% bond slash, auto-derived SLA.
