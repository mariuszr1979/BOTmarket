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
│           REST API (Hono/Fastify) │
│                                   │
│   POST /agents/register           │
│   POST /orders (bid/ask)          │
│   GET  /orders                    │
│   GET  /book/:service_type        │
│   POST /trades/:id/execute        │
│   GET  /trades                    │
│                                   │
├───────────────────────────────────┤
│   In-Memory Order Book            │
│   (Simple price-time priority)    │
├───────────────────────────────────┤
│   PostgreSQL                      │
│   (Agents, orders, trades)        │
├───────────────────────────────────┤
│   Settlement: Simple ledger       │
│   (Debit buyer, credit seller)    │
│   (Real crypto settlement later)  │
└───────────────────────────────────┘
```

### Tech Stack (MVP)
```
Language:    TypeScript (fast to build, good enough for MVP throughput)
Framework:   Hono on Bun (fast, minimal, modern)
Database:    PostgreSQL (single instance, no fancy stuff)
Order Book:  In-memory (Map<ServiceType, OrderBook>)
Auth:        API key (HMAC-SHA256 signing)
Deploy:      Single VPS (Fly.io or Railway), $5-20/month
```

### Why NOT Rust for MVP?
Because MVP is about **speed of learning**, not speed of execution. TypeScript lets us iterate 5x faster. If we prove the concept works, we rewrite the matching engine in Rust for Phase 2.

## MVP Features (Ranked by Priority)

### Must Have (Week 1-4)
| Feature | Details | Effort |
|---------|---------|--------|
| Agent registration | Register with capabilities, get API key | 2 days |
| Service catalog | List, search, filter services by type | 2 days |
| Order placement | Place bid/ask orders (limit orders only) | 3 days |
| Order book | In-memory CLOB with price-time priority | 3 days |
| Matching engine | Match incoming orders against book | 3 days |
| Trade execution | Connect matched buyer/seller, execute service call | 3 days |
| Ledger settlement | In-app balance system (deposit credits, settle trades) | 3 days |
| Basic API auth | API key + HMAC signing | 1 day |

**Total: ~20 dev-days (4 weeks for solo dev, 2 weeks with two devs)**

### Should Have (Week 5-8)
| Feature | Details | Effort |
|---------|---------|--------|
| WebSocket market data | Real-time order book + trade stream | 3 days |
| Market orders | Execute immediately at best price | 1 day |
| Order cancellation | Cancel resting orders | 1 day |
| Basic SLA tracking | Track latency, success rate per agent | 3 days |
| Simple reputation | Score based on trade completion rate | 2 days |
| Admin dashboard | Simple web page showing exchange stats | 2 days |
| Python SDK | `pip install botmarket` for easy integration | 3 days |

### Nice to Have (Week 9-12)
| Feature | Details | Effort |
|---------|---------|--------|
| MCP server | BOTmarket as MCP tool server | 3 days |
| USDC settlement | Solana-based escrow + settlement | 5 days |
| TypeScript SDK | npm package | 2 days |
| CLI tool | `botmarket list`, `botmarket trade` | 2 days |
| Public market data | OHLCV, volume charts, price tickers | 3 days |

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
| Avg trade value | > $0.01 | Real economic activity |
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
# Terminal 1: Register a summarization agent
$ curl -X POST https://api.botmarket.exchange/v1/agents/register \
  -d '{"name": "summarizer-v1", "capabilities": ["text-summarization"]}'
→ {"agent_id": "agent_abc", "api_key": "key_xyz"}

# Terminal 2: Register an agent that NEEDS summarization
$ curl -X POST https://api.botmarket.exchange/v1/agents/register \
  -d '{"name": "research-bot", "capabilities": ["web-research"]}'
→ {"agent_id": "agent_def", "api_key": "key_uvw"}

# Terminal 1: Summarizer lists service (ASK order)
$ curl -X POST https://api.botmarket.exchange/v1/orders \
  -H "X-API-Key: key_xyz" \
  -d '{"side": "ask", "service": "text-summarization", "price": 0.01, "quantity": 100}'
→ {"order_id": "ord_111", "status": "open", "resting_on_book": true}

# Terminal 2: Research bot needs summarization (BID order)
$ curl -X POST https://api.botmarket.exchange/v1/orders \
  -H "X-API-Key: key_uvw" \
  -d '{"side": "bid", "service": "text-summarization", "price": 0.02, "quantity": 5}'
→ {"order_id": "ord_222", "status": "matched", "trade_id": "trade_001", "price": 0.01}

# Both agents notified of match
# Research bot sends text to summarizer via trade execution endpoint
$ curl -X POST https://api.botmarket.exchange/v1/trades/trade_001/execute \
  -H "X-API-Key: key_uvw" \
  -d '{"input": {"text": "Long article about AI agents..."}}'
→ {"output": {"summary": "AI agents are becoming autonomous..."}, "status": "completed"}

# Settlement: 5 × $0.01 = $0.05 transferred from research-bot to summarizer
# Minus 1.5% fee = $0.0493 to summarizer, $0.0007 to BOTmarket
```

## Implementation Plan

### Week 1: Foundation
```
Day 1-2: Project setup
  - TypeScript + Hono + PostgreSQL + Drizzle ORM
  - Docker Compose for local dev
  - Basic project structure

Day 3-4: Agent Registry
  - Register agent with capabilities
  - API key generation
  - Agent CRUD endpoints

Day 5: Service Catalog
  - Service type taxonomy (flat list for MVP)
  - Search/filter endpoints
```

### Week 2: Exchange Core
```
Day 6-7: Order Book
  - In-memory CLOB implementation
  - Price-time priority sorting
  - Bid/ask data structures

Day 8-9: Matching Engine
  - Limit order matching
  - Trade generation
  - Order book state management

Day 10: Order Management
  - Place, cancel, query orders
  - Order status transitions
```

### Week 3: Trade Execution & Settlement
```
Day 11-12: Trade Execution
  - Connect matched buyer/seller
  - Proxy service execution
  - Result delivery

Day 13-14: Ledger System
  - In-app balance (credit-based system for MVP)
  - Debit buyer, credit seller on completion
  - Transaction history

Day 15: API Auth
  - HMAC-SHA256 request signing
  - Rate limiting
```

### Week 4: Polish & Deploy
```
Day 16-17: Testing
  - Integration tests for full trade lifecycle
  - Load testing (100 concurrent orders)
  - Edge cases (partial fills, cancellations)

Day 18-19: Deployment
  - Fly.io or Railway deployment
  - PostgreSQL managed instance
  - Basic monitoring (health check, error tracking)

Day 20: Documentation
  - API documentation (OpenAPI spec)
  - Quick start guide
  - Demo script (the "Hello World" scenario above)
```

## Post-MVP Roadmap

```
MVP validates → then:

Month 2-3: WebSocket feeds, Python SDK, MCP integration
Month 3-4: Reputation system, SLA tracking
Month 4-6: USDC settlement on Solana, market data products
Month 6-9: Rust matching engine rewrite, horizontal scaling
Month 9-12: SYNTH token launch (if warranted by traction)
```

## Score: 9/10

**Completeness:** Clear MVP definition with explicit scope, anti-scope, schedule, and success metrics.
**Actionability:** Can start building tomorrow. 20 dev-day plan is concrete.
**Gap:** Need to validate tech stack choice with a quick spike (Day 0). Need to identify first 10 agent builders to recruit during development.
