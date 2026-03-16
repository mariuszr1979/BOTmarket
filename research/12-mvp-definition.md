# Dimension 12: MVP Definition

## MVP Philosophy

The autoresearch principle: **constrain scope ruthlessly**. The MVP must answer exactly ONE question:

> **"Will AI agents trade services through an exchange mechanism?"**

If yes → iterate and expand.
If no → pivot or kill.

## What the MVP IS

```
A working exchange where:
1. An agent can list a service (place an ASK order)
2. Another agent can request that service (place a BID order)
3. The exchange matches bids and asks
4. The service is executed
5. Payment is settled
```

That's it. Everything else is noise at this stage.

## What the MVP is NOT

```
❌ A token/cryptocurrency
❌ A blockchain/Solana integration (USDC settlement later)
❌ A matching engine handling 1M orders/sec
❌ A beautiful web UI
❌ A mobile app
❌ A comprehensive API marketplace
❌ A reputation system
❌ A dispute resolution platform
❌ A governance system
❌ Multi-region infrastructure
```

## MVP Architecture

```
┌───────────────────────────────────┐
│  REST/JSON API (FastAPI)          │
│                                   │
│  POST /v1/agents/register         │
│  POST /v1/schemas/register        │
│  POST /v1/orders                  │
│  GET  /v1/book/:hash              │
│  POST /v1/trades/:id/execute      │
│  GET  /v1/stats/:pubkey           │
│                                   │
├───────────────────────────────────┤
│  Matching Engine (Python)          │
│  (Price-time priority per hash)   │
├───────────────────────────────────┤
│  Schema Registry                   │
│  (capability_hash → I/O schema)   │
├───────────────────────────────────┤
│  SQLite                            │
│  (Agents, orders, trades, CU      │
│   balances, schema registry)      │
├───────────────────────────────────┤
│  Settlement: CU Ledger             │
│  (Debit buyer CU, credit seller)  │
│  (USDC off-ramp deferred)         │
└───────────────────────────────────┘

Phase 2 upgrade path (when thesis validated):
  SQLite → PostgreSQL
  API key → Ed25519
  REST/JSON only → Binary TCP + JSON bridge
  Python/FastAPI → TypeScript/Hono/Bun (or keep Python)
  Single VPS → Fly.io multi-region
```

### Tech Stack (MVP)
```
Language:    Python (accessible to non-developers, AI-assistable, vast ecosystem)
Framework:   FastAPI (simple, well-documented, async support)
Database:    SQLite (zero config, single file, good enough for validation)
Order Book:  In-memory (dict[str, list] keyed by capability hash)
Protocol:    REST/JSON only (binary protocol is Phase 2 optimization)
Auth:        API key (Ed25519 cryptographic identity is Phase 2)
Deploy:      Local / single VPS ($5/month), $5-20/month
Currency:    Compute Units (CU) — internal ledger (simple balance table)
```

### Why Rescoped from Original Spec?
```
Original:  TypeScript + Hono + Bun + PostgreSQL + Drizzle + Binary TCP + Ed25519
Rescoped:  Python + FastAPI + SQLite + REST/JSON + API key

Reason:    Founder is a hobby AI user, not a developer/programmer.
           Original 22-day estimate assumed experienced TypeScript developer.
           Binary TCP, Ed25519, and PostgreSQL are deep engineering territory.
           AI coding assistants can write the code, but debugging, deploying,
           and maintaining production infra requires engineering experience.

What stays (the thesis validation):
  ✓ Schema-hash capability discovery (SHA-256 — 3 lines of Python)
  ✓ Order book concept (ASK/BID table in SQLite)
  ✓ Matching engine (find matching orders, execute)
  ✓ CU ledger (simple balance tracking)
  ✓ 1.5% fee deduction

What's deferred (engineering moat, not thesis validation):
  ✗ Binary TCP protocol → REST/JSON only (binary is optimization, not validation)
  ✗ Ed25519 crypto auth → API key (crypto identity is moat, not MVP)
  ✗ PostgreSQL → SQLite (no config, good enough for <1000 agents)
  ✗ In-memory CLOB → SQLite queries (slower but correct)
  ✗ Bun runtime → standard Python (more accessible)

What this still proves to investors:
  The same thing — agents can discover each other by capability hash
  and trade services through an exchange mechanism. The binary protocol
  and crypto identity are things you DESCRIBE to investors, not demo.
```

## MVP Features (Ranked by Priority)

### Must Have (Weekends 1-8, ~2-4 weekends with AI assistance)
| Feature | Details | Effort |
|---------|---------|--------|
| Agent registration | API key generation, register agent | 1 session |
| Schema registry | Register capability hashes (SHA-256 of I/O schemas) | 1 session |
| Order placement | Place bid/ask orders by capability hash, priced in CU | 1-2 sessions |
| Order book | SQLite-backed book keyed by capability hash, CU price-time priority | 1-2 sessions |
| Matching engine | Match incoming orders against book | 1-2 sessions |
| Trade execution | Connect matched buyer/seller, proxy JSON data | 1-2 sessions |
| CU Ledger | SQLite balance table (deposit CU, settle trades) | 1 session |
| REST API | FastAPI endpoints for all operations | included above |

**Total: ~8-16 sessions (2-4 weekends with AI coding assistance)**

Note: "session" = 3-4 hours of focused work with AI assistant. Previous estimate of
"22 dev-days (5 weeks solo)" assumed an experienced TypeScript developer building
binary TCP + PostgreSQL + Ed25519. This rescoped version is achievable for a
non-developer with AI assistance.

### Should Have (Week 5-8)
| Feature | Details | Effort |
|---------|---------|--------|
| WebSocket market data | Real-time order book + trade stream (binary) | 3 days |
| Market orders | Execute immediately at best price | 1 day |
| Order cancellation | Cancel resting orders | 1 day |
| Agent statistics tracking | Raw metrics: latency, compliance, trades (no aggregated "reputation score") | 2 days |
| Python SDK | `pip install botmarket` for easy integration | 3 days |
| Stats API | `/v1/stats/{pubkey}` returns raw observable metrics (JSON) | 2 days |

### Nice to Have (Week 9-12)
| Feature | Details | Effort |
|---------|---------|--------|
| MCP bridge | BOTmarket as MCP tool server (human bridge) | 3 days |
| TypeScript SDK | npm package | 2 days |
| CLI tool | `botmarket list`, `botmarket trade` (developer convenience) | 2 days |
| Framework integrations | LangChain, CrewAI tool providers | 3 days |
| CU bond enforcement | Auto-slash bond on schema violation | 2 days |

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
  - Agents trade but not through order books → maybe simpler marketplace
  - Only humans use it, not agents → pivot to API marketplace
  - Only one service type is popular → niche down to that vertical
```

## MVP Demo Scenario

### The "Hello World" of BOTmarket

```
# Agent A: Summarization service
# Generates Ed25519 keypair, registers on exchange

# Agent A registers its capability schema:
#   input:  { type: "text", encoding: "utf8", max_bytes: 100000 }
#   output: { type: "text", encoding: "utf8", max_bytes: 5000 }
#   capability_hash = SHA-256(input_schema || output_schema) = 0xd4e5...

# Via JSON bridge (for demo readability):
$ curl -X POST https://api.botmarket.exchange/v1/agents/register \
  -d '{"pubkey": "ed25519:7xKX..."}'
→ {"agent_id": "7xKX...", "cu_balance": 0}

$ curl -X POST https://api.botmarket.exchange/v1/schemas/register \
  -d '{"input": {"type":"text","encoding":"utf8"}, "output": {"type":"text","encoding":"utf8"}}'
→ {"capability_hash": "0xd4e5..."}

# Agent A places ASK: "I offer 0xd4e5... for 20 CU per call"
$ curl -X POST https://api.botmarket.exchange/v1/orders \
  -d '{"side": "ask", "capability_hash": "0xd4e5...", "price_cu": 20, "quantity": 100}'
→ {"order_id": "ord_111", "status": "open", "resting_on_book": true}

# Agent B needs capability 0xd4e5... (or searches by embedding)
$ curl -X POST https://api.botmarket.exchange/v1/orders \
  -d '{"side": "bid", "capability_hash": "0xd4e5...", "price_cu": 25, "quantity": 5}'
→ {"order_id": "ord_222", "status": "matched", "trade_id": "trade_001", "price_cu": 20}

# Execute: Agent B sends raw input bytes, Agent A returns raw output bytes
$ curl -X POST https://api.botmarket.exchange/v1/trades/trade_001/execute \
  -d '{"input": "Long article about AI agent commerce..."}'
→ {"output": "AI agents are forming autonomous markets...", "latency_ms": 145}

# Settlement: 5 × 20 CU = 100 CU transferred from B to A
# Minus 1.5% fee = 1.5 CU to BOTmarket
# Agent A receives: 98.5 CU

# Native binary protocol would do this in ~500 bytes total.
# JSON bridge adds ~10× overhead but works for demos.
```

## Implementation Plan

### Rescoped for Non-Developer with AI Assistance

```
Original plan: 22 dev-days, TypeScript + PostgreSQL + Binary TCP + Ed25519
Rescoped plan: 8-16 sessions (2-4 weekends), Python + SQLite + REST/JSON + API key

The original implementation plan below is preserved as a REFERENCE for the
full-spec build if an experienced developer joins. The rescoped stack in
the Tech Stack section above is what gets built first.
```

### Weekend 1: Foundation
```
Session 1: Project setup
  - Python + FastAPI + SQLite
  - Virtual environment + requirements.txt
  - Basic health check endpoint

Session 2: Agent Registry + Schema Registry
  - API key-based registration
  - Schema registration (I/O schema → SHA-256 capability hash)
  - Agent CRUD endpoints (REST/JSON)
  - Schema discovery (query by capability hash, exact match)
```

### Weekend 2: Exchange Core
```
Session 3: Order Book
  - SQLite-backed order storage keyed by capability hash
  - CU price-time priority sorting
  - Bid/ask endpoints

Session 4: Matching Engine + Order Management
  - Limit order matching
  - Trade generation
  - Place, cancel, query orders
  - Order status transitions
```

### Weekend 3: Trade Execution & Settlement
```
Session 5: Trade Execution
  - Connect matched buyer/seller via JSON payloads
  - Schema verification (output matches declared schema)
  - Latency measurement

Session 6: CU Ledger System
  - CU balance per agent (SQLite table)
  - Debit buyer CU, credit seller CU on completion
  - Fee deduction (1.5% in CU)
  - Transaction history
```

### Weekend 4: Test & Deploy
```
Session 7: Testing
  - Integration tests for full trade lifecycle
  - 2-3 test agents exercising the exchange
  - Edge cases (partial fills, cancellations, schema mismatches)

Session 8: Deployment
  - Deploy to single VPS or Fly.io
  - Basic monitoring (health check, error logging)
  - API documentation + quick start guide
```

### Full-Spec Reference Plan (For Experienced Developer, When Available)
```
The original TypeScript + PostgreSQL + Binary TCP + Ed25519 plan
is described below for reference. This is the Phase 2 engineering
upgrade path when the thesis is validated with the Python MVP.

Week 1: TypeScript + Hono + PostgreSQL + Drizzle + binary message types
Week 2: In-memory CLOB + matching engine + Ed25519 auth
Week 3: Binary TCP server + trade execution proxy + CU ledger
Week 4-5: JSON bridge + testing + Fly.io deployment
```

## Post-MVP Roadmap

```
MVP validates → then:

Month 2-3: Embedding-based fuzzy discovery, Python SDK, WebSocket feeds
Month 3-4: Framework integrations (LangChain, CrewAI, AutoGen)
Month 4-6: CU/USDC off-ramp, market data API products
Month 6-9: Rust matching engine rewrite, horizontal scaling
Month 9-12: Barter mode (direct service-for-service CU swaps)
```

## Score: 9/10

**Completeness:** Clear MVP with CU currency, schema-hash addressing, REST/JSON API, deterministic verification.
**Actionability:** Rescoped stack (Python/FastAPI/SQLite) is buildable by a non-developer with AI assistance. 2-4 weekends timeline is honest. No human infrastructure to build (no dashboards, no reputation system, no dispute resolution, no KYC, no badges).
**Gap:** Need to prototype schema-hash matching with real agents. Original full-spec plan preserved for Phase 2 when engineering talent joins.
**Note:** Score maintained at 9/10 — the MVP DESIGN (what's in vs out) remains tight. The rescoping actually improves feasibility by matching scope to founder profile. Binary protocol and Ed25519 are described to investors as the moat, built in Phase 2.
