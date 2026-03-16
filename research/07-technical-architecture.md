# Dimension 7: Technical Architecture

## Core Architecture Decision: Order Book vs AMM

### Order Book (Traditional Exchange Model)
```
Buyer places bid:  "I need image-classification, willing to pay $0.05/call, need <500ms latency"
Seller places ask: "I offer image-classification, price $0.04/call, <200ms latency"

Order Book:
  BIDS                          ASKS
  $0.05 x 100 calls (Agent A)  $0.04 x 500 calls (Agent X)
  $0.04 x 200 calls (Agent B)  $0.06 x 300 calls (Agent Y)
  $0.03 x 500 calls (Agent C)  $0.08 x 100 calls (Agent Z)

Match: Agent A's bid ($0.05) matches Agent X's ask ($0.04)
Execution price: $0.045 (midpoint) or $0.04 (price-time priority)
```

**Pros:** True price discovery, familiar model, deep liquidity possible
**Cons:** Complex to build, needs market makers to bootstrap, order management overhead

### AMM (Automated Market Maker — DeFi Style)
```
Liquidity Pool: Image-Classification Service Pool
  Reserve: 10,000 service credits × 500 USDC
  Price = USDC_reserve / Service_reserve = $0.05/call
  
Agent buys 100 calls:
  New price after purchase: $0.0505 (price moves with demand)
```

**Pros:** Always liquid, no market makers needed, simpler
**Cons:** Impermanent loss for LPs, less efficient pricing, slippage on large orders

### Hybrid (RECOMMENDED)
```
Primary:   Central Limit Order Book (CLOB) for popular services
Fallback:  AMM pools for long-tail/new services
Routing:   Smart order router picks best price across both
```

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        API Gateway                          │
│                    (Rate limiting, Auth)                     │
├──────────────┬───────────────┬──────────────┬───────────────┤
│  Order Mgmt  │  Matching     │  Settlement  │  Market Data  │
│  Service     │  Engine       │  Service     │  Service      │
│              │               │              │               │
│ - Place order│ - Price-time  │ - Escrow     │ - Order book  │
│ - Cancel     │   priority    │ - Execute    │ - Tick data   │
│ - Modify     │ - CLOB + AMM  │ - Confirm    │ - OHLCV       │
│ - Query      │ - Cross-match │ - Dispute    │ - WebSocket   │
├──────────────┴───────────────┴──────────────┴───────────────┤
│                     Agent Registry                          │
│            (Identity, Capabilities, SLAs, Reputation)       │
├─────────────────────────────────────────────────────────────┤
│                    Service Catalog                          │
│           (Categories, Schemas, Pricing, Benchmarks)        │
├──────────────┬──────────────────────────────────────────────┤
│  Blockchain  │  Database Layer                              │
│  Layer       │                                              │
│              │  PostgreSQL:   Orders, trades, accounts      │
│  Solana:     │  Redis:        Order books, sessions, cache  │
│  - Settlement│  ClickHouse:   Market data, analytics        │
│  - Escrow    │  S3/Minio:     Agent artifacts, logs         │
│  - Identity  │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

## Matching Engine Design

The matching engine is the **heart** of BOTmarket — must be fast, fair, and reliable.

### Requirements
```
Latency:       < 1ms per match (in-memory)
Throughput:     100K matches/sec (target)
Fairness:      Price-time priority (FIFO at same price level)
Availability:   99.99% uptime
Consistency:    No double-fills, no phantom orders
```

### Data Structures
```
Order Book per Service Category:

struct OrderBook {
    service_id: ServiceId,
    bids: BTreeMap<Price, VecDeque<Order>>,  // Sorted desc by price
    asks: BTreeMap<Price, VecDeque<Order>>,  // Sorted asc by price
    best_bid: Option<Price>,
    best_ask: Option<Price>,
    spread: Option<Price>,
}

struct Order {
    order_id: Uuid,
    agent_id: AgentId,
    side: Side,           // Bid or Ask
    order_type: OrderType, // Market, Limit, IOC, FOK
    price: Price,
    quantity: u64,         // Number of service calls
    remaining: u64,
    timestamp: u64,        // Nanosecond precision
    sla: SlaRequirements,
}
```

### Order Types
| Type | Behavior | Use Case |
|------|----------|----------|
| Market | Execute immediately at best price | "I need this NOW" |
| Limit | Execute at specified price or better | "I'll wait for a good price" |
| IOC (Immediate or Cancel) | Fill what you can, cancel rest | Partial fills OK |
| FOK (Fill or Kill) | Fill entirely or not at all | All-or-nothing |
| Stop | Trigger at price threshold | Auto-purchase when cheap |

### Matching Algorithm
```
fn match_order(book: &mut OrderBook, incoming: Order) -> Vec<Trade> {
    if incoming.side == Bid {
        // Match against asks (lowest first)
        while incoming.remaining > 0 && book.best_ask <= incoming.price {
            let ask = book.asks.front();
            let fill_qty = min(incoming.remaining, ask.remaining);
            let fill_price = ask.price;  // Price-time priority: taker gets maker's price
            
            trades.push(Trade { buyer: incoming, seller: ask, qty: fill_qty, price: fill_price });
            
            incoming.remaining -= fill_qty;
            ask.remaining -= fill_qty;
            if ask.remaining == 0 { book.asks.remove(ask); }
        }
        if incoming.remaining > 0 && incoming.order_type == Limit {
            book.bids.insert(incoming);  // Rest on book
        }
    }
    trades
}
```

## Technology Stack

### Core Services (Rust)
```
Matching Engine:    Rust — performance-critical, zero-copy, lock-free
Order Management:   Rust — tight integration with matching engine
Settlement:         Rust — Solana program (Anchor framework)
```

### Application Services (TypeScript/Node.js or Go)
```
API Gateway:        TypeScript (Fastify/Hono) or Go — REST + WebSocket
Agent Registry:     TypeScript — CRUD operations, not performance-critical
Service Catalog:    TypeScript — Search, categorization
Market Data:        Go or Rust — high-throughput tick data streaming
```

### Infrastructure
```
Database:           PostgreSQL 16 (primary), Redis 7 (cache/pub-sub)
Message Queue:      NATS or Kafka (order flow, event sourcing)
Analytics:          ClickHouse (market data, time-series)
Search:             Meilisearch or Typesense (agent/service discovery)
Container:          Docker + Kubernetes (or Fly.io for simplicity)
CI/CD:              GitHub Actions
Monitoring:         Prometheus + Grafana + OpenTelemetry
```

### Why Rust for Matching Engine?
```
1. Zero-cost abstractions — no GC pauses
2. Memory safety without overhead
3. Fearless concurrency
4. < 1μs order matching
5. Deterministic performance
6. Solana programs are written in Rust
7. The entire exchange core can be one language
```

### Why NOT Rust for Everything?
```
1. Slower dev velocity for CRUD operations
2. TypeScript ecosystem is massive for web APIs
3. Easier to hire TypeScript devs
4. Prototyping is faster in TS/Go
```

## Agent-to-Exchange Communication

### Protocol: REST + WebSocket + MCP

```
REST API:
  POST   /v1/orders          — Place order
  DELETE /v1/orders/{id}     — Cancel order
  GET    /v1/orders          — List orders
  GET    /v1/services/{id}   — Service info
  GET    /v1/agents/{id}     — Agent info
  POST   /v1/agents/register — Register agent

WebSocket:
  ws://exchange/v1/stream
  Subscribe to: order_book, trades, ticker, agent_status

MCP Integration:
  BOTmarket as MCP server → any MCP-compatible agent can trade
  Tools: place_order, cancel_order, get_book, list_services
```

### Agent Authentication
```
1. Agent registers → receives API key + secret
2. Each request signed with HMAC-SHA256 (like Binance API)
3. Optional: Solana wallet-based auth (sign challenge with private key)
4. Rate limits per agent: 100 req/sec (adjustable with tier)
```

## Data Flow: Complete Trade Lifecycle

```
1. Agent A registers as service provider
   → Submits: capability descriptor, SLA, pricing
   → Gets: agent_id, API key, certificate

2. Agent A places ASK order
   → "Offering image-classification, $0.04/call, <200ms, 99.5% accuracy"
   → Order enters matching engine → rests on order book

3. Agent B needs image-classification
   → Queries service catalog → finds image-classification
   → Places BID: "Need image-classification, willing to pay $0.05/call"

4. Matching engine matches A's ask with B's bid
   → Trade created at $0.04 (maker price)
   → Both agents notified via WebSocket

5. Settlement
   → Smart contract creates escrow
   → Agent B deposits $0.04 USDC
   → Agent B sends image to Agent A
   → Agent A processes, returns classification
   → Verification: result checked against SLA
   → If SLA met: $0.04 released to Agent A (minus fees)
   → If SLA violated: dispute process triggered

6. Post-trade
   → Trade recorded on-chain (settlement proof)
   → Market data updated (last price, volume)
   → Agent reputations updated
   → Order book snapshot stored
```

## Scalability Considerations

### Phase 1: MVP (< 1,000 agents)
```
Single server, PostgreSQL, in-memory order book
Latency: < 10ms per match
Throughput: 1K matches/sec
Cost: $50-100/mo (single VPS)
```

### Phase 2: Growth (1K-100K agents)
```
Horizontal scaling with NATS message bus
Separate read/write databases
Redis cluster for order books
Throughput: 100K matches/sec
Cost: $1K-5K/mo
```

### Phase 3: Scale (100K+ agents)
```
Dedicated matching engine servers
Sharded order books by service category
Multi-region deployment
Throughput: 1M+ matches/sec
Cost: $10K-50K/mo
```

## Score: 8/10

**Completeness:** Covers architecture, matching engine, tech stack, scalability.
**Actionability:** Clear technology choices with rationale.
**Gap:** Need benchmarks for Rust matching engine. Need to detail Solana program architecture for settlement. Need to validate NATS vs Kafka decision with POC.
