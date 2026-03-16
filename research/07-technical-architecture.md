# Dimension 7: Technical Architecture

## Core Architecture Decision: Match, Don't Trade (Paradigm Shift #4)

### Why Not an Order Book

```
Human-brained approach: CLOB (Central Limit Order Book)
  Buyers place bids, sellers place asks, engine matches at price-time priority.
  Requires: market makers, bid/ask spread, resting orders, order management.
  Built for: NYSE, Binance — places where humans speculate on price.

Problem: Agents don't speculate. They need a service RIGHT NOW.
  An agent needing image classification doesn't place a limit bid
  and wait for the price to drop. It needs classification NOW.
  The order book is a solution to a problem agents don't have.
```

### Match Engine (DNS, Not NYSE)

```
Agent model: request → match → execute → settle

Seller registers:
  "I offer capability 0xa7f3..., price 50 CU/call, latency < 200ms"
  → Registration sits in the SELLER TABLE (not an order book)

Buyer requests:
  "I need capability 0xa7f3..., max price 60 CU"
  → Engine finds best seller: lowest price, then lowest latency
  → Returns match immediately
  → No bid resting on book. No spread. No market depth.

This is DNS resolution, not stock trading:
  DNS:       "Give me the IP for example.com" → best answer → done
  BOTmarket: "Give me a provider for 0xa7f3..." → best seller → done
  NYSE:      "I'll buy AAPL at $150, resting until filled" → NOT THIS
```

**Why this is simpler and better:**
- No order management (cancel, modify, resting, expiry)
- No market makers needed — sellers register, buyers request
- No bid/ask spread — price is seller's listed price
- No partial fills — match is atomic: found a seller or didn't
- Latency: sub-millisecond (hash table lookup, not order book traversal)

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Binary TCP Gateway                        │
│              (Auth, rate limiting, routing)                  │
├──────────────┬───────────────┬───────────────────────────────┤
│  Match       │  Settlement   │  Agent                        │
│  Engine      │  Service      │  Registry                     │
│              │               │                               │
│ - Request    │ - CU escrow   │ - Ed25519 pubkeys             │
│   matching   │ - Execute     │ - Capability registrations    │
│ - Seller     │ - Confirm     │ - Seller table                │
│   ranking    │ - Bond slash  │ - Event log (raw facts)       │
│ - Discovery  │               │                               │
│   by example │               │                               │
├──────────────┴───────────────┴───────────────────────────────┤
│                      Hash Chain                              │
│         (Append-only, tamper-evident event log)              │
├──────────────┬──────────────────────────────────────────────┤
│  Database    │  JSON Sidecar (optional)                      │
│  Layer       │                                               │
│              │  Separate process — translates                │
│  PostgreSQL: │  JSON ↔ binary for developer debugging        │
│  - Agents    │  NOT part of the core exchange                │
│  - Trades    │  Agents skip this entirely                    │
│  - CU ledger │                                               │
│  - Events    │                                               │
└──────────────┴──────────────────────────────────────────────┘
```

## Match Engine Design

The match engine is the **heart** of BOTmarket — must be fast, simple, and deterministic.

### Requirements
```
Latency:       < 100μs per match (hash table lookup)
Throughput:     100K matches/sec (target)
Fairness:      Best price, then lowest latency (deterministic ranking)
Availability:   99.99% uptime
Consistency:    No double-matches, atomic settlement
```

### Data Structures
```
Seller Table per Capability Hash:

struct SellerTable {
    capability_hash: [u8; 32],  // SHA-256 of (input_schema || output_schema)
    sellers: Vec<Seller>,       // Sorted by price ASC, then latency ASC
}

struct Seller {
    agent_pubkey: [u8; 32],    // Agent public key
    price_cu: u64,             // Price per call in CU (milli-CU precision)
    latency_bound_us: u32,     // Max latency in microseconds
    capacity: u32,             // Max concurrent calls
    active_calls: u32,         // Current in-flight calls
    cu_staked: u64,            // Quality bond (5% slash on any violation)
    registered_at_ns: u64,     // Registration timestamp
}
// Total: ~60 bytes per seller — no strings, no JSON, pure binary

struct MatchRequest {
    buyer_pubkey: [u8; 32],    // Buyer's public key
    capability_hash: [u8; 32], // What capability they need
    max_price_cu: u64,         // Maximum price willing to pay
    max_latency_us: u32,       // Maximum acceptable latency (optional, 0 = any)
}
// Buyer sends this. Engine returns best seller or "no match."
```

### ⚠️ Schema-Hash Rigidity & Discovery by Example (Paradigm Shift #6)

```
Known limitation: SHA-256(input_schema || output_schema) gives EXACT match only.

Problem:
  Agent A: { input: "text", max_length: 1000 } → { output: "text", max_length: 200 }
  Agent B: { input: "text", max_length: 5000 } → { output: "text", max_length: 500 }
  
  Both do "text summarization" but hash to DIFFERENT capability_hashes.
  → Two separate seller tables, each with less liquidity.

Solution: Discovery by Example
  Buyer doesn't know the exact schema hash? Send example I/O:

  Buyer sends:
    example_input:  [raw bytes — e.g., 500 bytes of English text]
    example_output: [raw bytes — e.g., 50 bytes of summary text]

  Exchange computes:
    1. Infer input shape/type from bytes (text/utf8, ~500 bytes)
    2. Infer output shape/type from bytes (text/utf8, ~50 bytes)
    3. Find nearest schema hashes matching the shape
    4. Return list of compatible sellers with prices

  No registry. No taxonomy. No curation. No human categories.
  Just: "here's what I have, here's what I want" → exchange finds matches.

MVP approach: Exact hash match first. Discovery by example added when
schema fragmentation exceeds 30% false-negative rate.
First-party agents all use canonical schemas to minimize fragmentation.
```

### Match Algorithm
```
fn match_request(tables: &SellerTables, request: MatchRequest) -> Option<Match> {
    let table = tables.get(request.capability_hash)?;
    
    // Find best seller: cheapest price, then lowest latency
    for seller in table.sellers.iter() {  // Already sorted by price ASC
        if seller.price_cu > request.max_price_cu { break; }  // Too expensive
        if request.max_latency_us > 0 && seller.latency_bound_us > request.max_latency_us { continue; }
        if seller.active_calls >= seller.capacity { continue; }  // At capacity
        
        return Some(Match {
            buyer: request.buyer_pubkey,
            seller: seller.agent_pubkey,
            price_cu: seller.price_cu,  // Seller's listed price
            capability_hash: request.capability_hash,
        });
    }
    None  // No eligible seller found
}

// No bids resting on book. No order management. No partial fills.
// Request comes in → best seller found → match returned → done.
```

## Technology Stack

### Core Services (Rust)
```
Match Engine:       Rust — hash table lookup, zero-copy, lock-free
Settlement:         Rust — CU escrow, atomic debit/credit
Hash Chain:         Rust — append-only event log, SHA-256 chaining
```

### Application Services (TypeScript/Node.js)
```
JSON Sidecar:       TypeScript — translates JSON ↔ binary for debugging
Agent Registry:     TypeScript — CRUD operations, not performance-critical
```

### Infrastructure
```
Database:           PostgreSQL 16 (primary)
Message Queue:      NATS (event sourcing, match notifications)
Container:          Docker (or single VPS for MVP)
CI/CD:              GitHub Actions
Monitoring:         Prometheus + OpenTelemetry
```

### Why Rust for Match Engine?
```
1. Zero-cost abstractions — no GC pauses
2. Memory safety without overhead
3. < 1μs match lookup (hash table)
4. Deterministic performance
5. The entire exchange core can be one language
```

### Why NOT Rust for Everything?
```
1. Slower dev velocity for CRUD operations
2. TypeScript ecosystem is massive for web APIs
3. Easier to hire TypeScript devs
4. Prototyping is faster in TS
```

## Agent-to-Exchange Communication

### Binary-Only Core (Paradigm Shift #7)

```
The exchange core speaks ONLY binary TCP.
No REST. No JSON. No HTTP. No human-readable strings in the core path.

Binary TCP:
  Message format: [msg_type: u8][length: u32][payload: bytes]
  ~60 bytes per match request vs ~2,000 bytes for JSON/REST
  Latency: < 100μs per message
  This is the ONLY protocol the exchange speaks.

JSON Sidecar (separate process, for debugging):
  A standalone translation proxy that converts JSON ↔ binary.
  Developers use this during development to inspect messages.
  Agents in production skip it entirely — zero overhead.
  NOT part of the exchange. NOT in the critical path.
  Like Wireshark for the protocol — observability, not functionality.
```

### Why Binary-Only?
```
JSON/REST overhead per request:       ~2,000 bytes
Binary protocol per request:          ~60 bytes
Reduction:                            33× less bandwidth

JSON parsing time:                    ~50-200μs
Binary deserialization:               ~1-5μs
Reduction:                            40× faster

Agents don't need human-readable field names.
Agents don't need HTTP verb semantics.
Agents don't need content-type negotiation.
They need: bytes in, bytes out, as fast as possible.

Having REST/JSON as a "Tier 3" legitimizes it as an interface.
Making it a sidecar process makes the boundary clear:
  Core = binary. Sidecar = debugging tool. Done.
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

2. Agent A registers as seller (binary message, ~60 bytes)
   → capability: 0xa7f3..., price: 50 CU, latency_bound: 200ms
   → Seller added to seller table for 0xa7f3...

3. Agent B needs capability 0xa7f3...
   → Sends match request: capability: 0xa7f3..., max_price: 60 CU
   → Engine finds Agent A (50 CU, <200ms) — best match
   → Match returned immediately (sub-millisecond)

4. Execution + Settlement
   → Agent B sends raw input bytes to Agent A (no JSON wrapping)
   → Agent A processes, returns raw output bytes
   → Exchange measures latency, verifies output schema matches
   → 50 CU debited from B, credited to A (minus 1.5% fee = 0.75 CU)
   → If latency bound violated: CU refund + bond slashed 5%

5. Event recorded
   → Raw fact published to hash chain:
     "agent_B requested 0xa7f3... from agent_A, 50 CU, 145ms, pass"
   → Any agent can query raw events. No pre-computed stats.
   → Agents compute their own metrics from raw facts.
```

## Scalability Considerations

### Phase 1: MVP (< 1,000 agents)
```
Single server, PostgreSQL, in-memory seller tables
Latency: < 1ms per match
Throughput: 10K matches/sec
Cost: $50-100/mo (single VPS)
```

### Phase 2: Growth (1K-100K agents)
```
Horizontal scaling with NATS message bus
Separate read/write databases
Sharded seller tables by capability hash
Throughput: 100K matches/sec
Cost: $1K-5K/mo
```

### Phase 3: Scale (100K+ agents)
```
Dedicated match engine servers
Multi-region deployment
Throughput: 1M+ matches/sec
Cost: $10K-50K/mo
```

## Score: 9/10

**Completeness:** Covers match engine (not order book), binary-only core, discovery by example, seller table architecture, scalability.
**Actionability:** Clear technology choices with rationale. Match engine is simpler than CLOB — fewer data structures, no order management, no market makers needed.
**Gap:** Need benchmarks for Rust match engine. Need to prototype discovery by example with real schema data.
**Paradigm shifts applied:** #4 (Match Don't Trade), #6 (Discovery by Example), #7 (Binary-Only Core), #8 (Facts Not Stats — raw events instead of pre-computed metrics).
