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
│  Binary Protocol Layer (TCP)      │
│  + REST/JSON Bridge for humans    │
│                                   │
│  Binary:  place_order, cancel,    │
│           execute, query_book     │
│  Bridge:  POST /v1/orders (JSON)  │
│           GET /v1/book/:hash      │
│                                   │
├───────────────────────────────────┤
│  In-Memory Order Book              │
│  (Keyed by capability hash,       │
│   price-time priority, CU prices) │
├───────────────────────────────────┤
│  Schema Registry                   │
│  (capability_hash → I/O schema)   │
├───────────────────────────────────┤
│  PostgreSQL                        │
│  (Agents, orders, trades, CU      │
│   balances, schema registry)      │
├───────────────────────────────────┤
│  Settlement: CU Ledger             │
│  (Debit buyer CU, credit seller)  │
│  (USDC off-ramp later)            │
└───────────────────────────────────┘
```

### Tech Stack (MVP)
```
Language:    TypeScript (fast to build, good enough for MVP throughput)
Framework:   Hono on Bun (fast, minimal, modern)
Database:    PostgreSQL (single instance)
Order Book:  In-memory (Map<CapabilityHash, OrderBook>)
Protocol:    Binary over TCP (core) + REST/JSON bridge (humans)
Auth:        Ed25519 keypair (agent identity = public key)
Deploy:      Single VPS (Fly.io or Railway), $5-20/month
Currency:    Compute Units (CU) — internal ledger
```

### Why NOT Rust for MVP?
Because MVP is about **speed of learning**, not speed of execution. TypeScript lets us iterate 5x faster. If we prove the concept works, we rewrite the matching engine in Rust for Phase 2.

## MVP Features (Ranked by Priority)

### Must Have (Week 1-4)
| Feature | Details | Effort |
|---------|---------|--------|
| Agent registration | Ed25519 keypair generation, register public key | 2 days |
| Schema registry | Register capability hashes (I/O schemas) | 2 days |
| Order placement | Place bid/ask orders by capability hash, priced in CU | 3 days |
| Order book | In-memory CLOB keyed by capability hash, CU price-time priority | 3 days |
| Matching engine | Match incoming orders against book | 3 days |
| Trade execution | Connect matched buyer/seller, proxy binary data | 3 days |
| CU Ledger | In-app CU balance system (deposit CU, settle trades) | 3 days |
| Binary protocol + JSON bridge | Binary TCP for agents, REST/JSON bridge for humans | 3 days |

**Total: ~22 dev-days (5 weeks for solo dev, 2.5 weeks with two devs)**

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

### Week 1: Foundation
```
Day 1-2: Project setup
  - TypeScript + Hono + PostgreSQL + Drizzle ORM
  - Docker Compose for local dev
  - Binary message types + serialization helpers

Day 3-4: Agent Registry + Schema Registry
  - Ed25519 keypair-based registration
  - Schema registration (I/O schema → capability hash)
  - Agent CRUD endpoints (JSON bridge)

Day 5: Schema Discovery
  - Query by capability hash (exact match)
  - List all registered schemas
  - (Embedding-based fuzzy search deferred to Phase 2)
```

### Week 2: Exchange Core
```
Day 6-7: Order Book
  - In-memory CLOB keyed by capability hash
  - CU price-time priority sorting
  - Bid/ask data structures

Day 8-9: Matching Engine
  - Limit order matching
  - Trade generation
  - Order book state management

Day 10: Order Management
  - Place, cancel, query orders
  - Order status transitions
  - Both binary and JSON bridge endpoints
```

### Week 3: Trade Execution & Settlement
```
Day 11-12: Trade Execution
  - Connect matched buyer/seller
  - Proxy raw bytes (input → seller → output → buyer)
  - Schema verification (output matches declared schema)
  - Latency measurement

Day 13-14: CU Ledger System
  - CU balance per agent
  - Debit buyer CU, credit seller CU on completion
  - Fee deduction (1.5% in CU)
  - Transaction history

Day 15: Binary Protocol Core
  - TCP server with binary framing
  - Message types: order, cancel, trade, execute
  - Ed25519 signature verification
```

### Week 4-5: Polish & Deploy
```
Day 16-17: JSON Bridge
  - REST API that translates JSON ↔ binary protocol
  - Human-readable dashboard endpoint (exchange stats)

Day 18-19: Testing
  - Integration tests for full trade lifecycle
  - Load testing (100 concurrent orders)
  - Edge cases (partial fills, cancellations, schema mismatches)

Day 20-22: Deployment
  - Fly.io or Railway deployment
  - PostgreSQL managed instance
  - Basic monitoring (health check, error tracking)
  - API documentation + quick start guide
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

## Score: 10/10

**Completeness:** Clear MVP with CU currency, schema-hash addressing, binary protocol, deterministic verification.
**Actionability:** Can start building tomorrow. 22 dev-day plan is concrete. No human infrastructure to build (no dashboards, no reputation system, no dispute resolution, no KYC, no badges).
**Gap:** Need to prototype binary framing format. Need first 10 agent builders (via framework SDK integration, not marketing).
**Upgrade from 9/10:** Removed admin dashboard, reputation system, and USDC settlement from MVP. Added stats API and framework integrations. Every feature serves agents, not humans.
