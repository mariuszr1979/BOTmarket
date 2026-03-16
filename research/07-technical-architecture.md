# Dimension 7: Technical Architecture

## Core Architecture Decision: Order Book vs AMM

### Order Book (Traditional Exchange Model)
```
Buyer places bid:  "I need capability 0xa7f3..., willing to pay 60 CU/call, need <500ms"
Seller places ask: "I offer capability 0xa7f3..., price 50 CU/call, <200ms"

Order Book for capability 0xa7f3... (image tensor → label vector):
  BIDS                          ASKS
  60 CU x 100 calls (Agent A)  50 CU x 500 calls (Agent X)
  55 CU x 200 calls (Agent B)  65 CU x 300 calls (Agent Y)
  45 CU x 500 calls (Agent C)  80 CU x 100 calls (Agent Z)

Match: Agent A's bid (60 CU) matches Agent X's ask (50 CU)
Execution price: 50 CU (price-time priority — taker gets maker's price)
```

**Pros:** True price discovery, familiar model, deep liquidity possible
**Cons:** Complex to build, needs market makers to bootstrap, order management overhead

### AMM (Automated Market Maker — DeFi Style)
```
Liquidity Pool: Capability 0xa7f3... Pool
  Reserve: 10,000 service credits × 500,000 CU
  Price = CU_reserve / Service_reserve = 50 CU/call
  
Agent buys 100 calls:
  New price after purchase: 50.5 CU (price moves with demand)
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
Order Book per Capability Hash:

struct OrderBook {
    capability_hash: [u8; 32],  // SHA-256 of (input_schema || output_schema)
    bids: BTreeMap<CU, VecDeque<Order>>,  // Sorted desc by CU price
    asks: BTreeMap<CU, VecDeque<Order>>,  // Sorted asc by CU price
    best_bid: Option<CU>,
    best_ask: Option<CU>,
    spread: Option<CU>,
}

struct Order {
    order_id: u128,
    agent_id: [u8; 32],   // Agent public key
    side: u8,             // 0 = Bid, 1 = Ask
    order_type: u8,       // 0 = Market, 1 = Limit, 2 = IOC, 3 = FOK
    price_cu: u64,        // Price in CU (milli-CU precision)
    quantity: u64,        // Number of service calls
    remaining: u64,
    timestamp_ns: u64,    // Nanosecond precision
    latency_bound_us: u32, // Max latency in microseconds
}
// Total: 78 bytes per order — no strings, no JSON, pure binary
// No min_reputation field — buyers filter using raw stats, not scores
```

### ⚠️ Schema-Hash Rigidity & Liquidity Fragmentation

```
Known limitation: SHA-256(input_schema || output_schema) gives EXACT match only.

Problem:
  Agent A: { input: "text", max_length: 1000 } → { output: "text", max_length: 200 }
  Agent B: { input: "text", max_length: 5000 } → { output: "text", max_length: 500 }
  
  Both do "text summarization" but hash to DIFFERENT capability_hashes.
  → Two separate order books, each with less liquidity.
  → At low agent counts (<100), this fragments the market.

Mitigation strategy (design for now, build later):
  1. Schema registry stores full schemas, not just hashes
  2. Embedding index on schemas enables fuzzy search (Phase 2)
  3. Schema "families" — exchange can suggest: "0xa7f3... is similar to 0xb1e2..."
  4. Agents can list on multiple compatible schema hashes
  5. Cross-book matching: if schemas are structurally compatible 
     (superset input, subset output), exchange could cross-match

MVP approach: Exact match only. First-party agents all use canonical schemas.
Track false-negative rate (queries with 0 matches where similar schemas exist).
If fragmentation is >30%, prioritize embedding-based discovery.
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

### Three Protocol Tiers

```
Tier 1: BINARY PROTOCOL (native — fastest, for agents)
  TCP connection with binary framing
  No JSON, no HTTP overhead, no human-readable strings
  Message format: [msg_type: u8][length: u32][payload: bytes]
  ~100 bytes per order vs ~2,000 bytes for JSON/REST
  Latency: < 100μs per message

Tier 2: WEBSOCKET (real-time streaming)
  Binary WebSocket frames (not JSON text frames)
  Subscribe to: order_book_delta, trades, capability_updates
  Used for market data feeds and event streams

Tier 3: REST/JSON BRIDGE (for humans and legacy integration)
  Traditional REST API for human dashboards, debugging, MCP bridge
  Translates human-readable requests ↔ binary protocol
  POST /v1/orders, GET /v1/book/:capability_hash, etc.
  MCP server adapter: wraps binary protocol as MCP tools
```

### Why Binary-First?
```
JSON/REST overhead per order:         ~2,000 bytes
Binary protocol per order:            ~100 bytes
Reduction:                            20× less bandwidth

JSON parsing time:                    ~50-200μs
Binary deserialization:               ~1-5μs
Reduction:                            40× faster

Agents don't need human-readable field names.
Agents don't need HTTP verb semantics.
Agents don't need content-type negotiation.
They need: bytes in, bytes out, as fast as possible.
```

### Agent Authentication
```
1. Agent generates Ed25519 keypair (agent identity = public key)
2. Each message signed with private key (64 bytes)
3. Exchange verifies signature against registered public key
4. No API keys, no secrets to manage — cryptographic identity
5. Rate limits per agent: 1,000 msg/sec (adjustable with tier)
```

## Data Flow: Complete Trade Lifecycle

```
1. Agent A registers on exchange
   → Submits: Ed25519 public key + capability hashes (schema of what it can do)
   → Capability hash = SHA-256(input_schema || output_schema)
   → e.g., 0xa7f3... = hash([tensor:224×224×3,f32] || [vector:1000,f32])
   → No human-readable names needed — the schema IS the description

2. Agent A places ASK order (binary message, ~82 bytes)
   → capability: 0xa7f3..., price: 50 CU, latency_bound: 200ms
   → Order enters matching engine → rests on order book

3. Agent B needs capability 0xa7f3...
   → Queries by schema hash (or embedding similarity for fuzzy match)
   → Places BID: capability: 0xa7f3..., max_price: 60 CU, quantity: 100

4. Matching engine matches A's ask with B's bid
   → Trade created at 50 CU (maker price)
   → Both agents notified via binary WebSocket frame (~40 bytes)

5. Execution + Settlement
   → Agent B sends raw input bytes to Agent A (no JSON wrapping)
   → Agent A processes, returns raw output bytes
   → Exchange measures latency, verifies output schema matches
   → 50 CU debited from B, credited to A (minus 1.5% fee = 0.75 CU)
   → If latency bound violated: partial CU refund + reputation adjustment

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
Sharded order books by capability hash
Multi-region deployment
Throughput: 1M+ matches/sec
Cost: $10K-50K/mo
```

## Score: 9/10

**Completeness:** Covers architecture, matching engine, tech stack, scalability, and machine-native protocol.
**Actionability:** Clear technology choices with rationale. Binary protocol + CU pricing are concrete.
**Gap:** Need benchmarks for Rust matching engine. Need to prototype binary framing format.
**Upgrade from 8/10:** Binary protocol layer and CU-denominated order books make this genuinely differentiated from competitor architectures.
**Gap:** Need benchmarks for Rust matching engine. Need to detail Solana program architecture for settlement. Need to validate NATS vs Kafka decision with POC.
