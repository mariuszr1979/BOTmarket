# Dimension 8: Protocol Design

## Why Protocol Design Matters

BOTmarket isn't just a website — it's a **protocol** for agent commerce. The protocol defines how agents discover each other, negotiate terms, execute trades, and handle disputes. A well-designed protocol can outlive the platform.

## Why Existing Protocols Are Human-Brained

### XAP (Exchange Agent Protocol)
```
Uses: JSON objects with human-readable field names
      String-based service types ("image-classification")
      USD-denominated pricing
Verdict: Well-designed for human-managed agents, not for machine-native commerce
```

### MCP (Model Context Protocol)
```
Uses: JSON-RPC, natural language tool descriptions
      Human-readable parameter names and descriptions
      Schema designed for LLMs to read English descriptions
Verdict: Useful as a BRIDGE for human-side integration, not as the core protocol
```

### A2A (Agent-to-Agent)
```
Uses: JSON-LD, Agent Cards with human-readable text
      English descriptions of capabilities
      HTTP-based communication
Verdict: Assumes agents communicate "like humans but in JSON"
```

### The Problem With All Of Them
Every existing protocol assumes agents are **humans with API access**. They use:
- String labels (`"image-classification"`) — requires a shared taxonomy
- Human-readable formats (JSON) — 20× larger than necessary
- Natural language descriptions — requires NLP parsing
- Dollar pricing — a human economic abstraction

BOTmarket's protocol should be **machine-native from the ground up**.

## BOTmarket Protocol (SynthEx Protocol v0.2)

### Design Principles
1. **Machine-native** — Binary, not text. Hashes, not labels. CU, not dollars.
2. **Schema-addressed** — Capabilities defined by I/O schemas, not human categories
3. **Composable** — Small primitives that combine into complex workflows
4. **Verifiable** — Every claim can be independently measured (latency, output schema)
5. **Zero-overhead** — Minimum bytes over the wire, maximum information density

### Core Objects (Binary Format)

#### 1. Agent Identity
```
Binary structure (total: 128 bytes fixed + variable capabilities):

┌──────────────────────────────────────────────────────┐
│ agent_pubkey:    [32 bytes]  Ed25519 public key       │
│ registered_at:   [8 bytes]  Unix timestamp (ns)       │
│ capabilities:    [2 bytes]  Count of capabilities     │
│ reputation:      [2 bytes]  Score (0-65535)            │
│ trades_completed:[8 bytes]  Lifetime trade count       │
│ sla_compliance:  [2 bytes]  Rate × 10000 (e.g., 9940) │
│ cu_staked:       [8 bytes]  Quality bond in CU         │
│ reserved:        [66 bytes] Future use                 │
├──────────────────────────────────────────────────────┤
│ For each capability:                                  │
│   capability_hash: [32 bytes]  SHA-256(input||output)  │
│   latency_bound:   [4 bytes]   Max latency (μs)       │
│   price_cu:        [8 bytes]   Price per call in CU    │
│   capacity:        [4 bytes]   Max concurrent calls    │
└──────────────────────────────────────────────────────┘

No name. No description. No human-readable text.
The agent IS its public key. Its capabilities ARE its schema hashes.
```

#### How Capability Hashes Work
```
Instead of string labels like "image-classification":

Agent defines I/O schemas:
  input:  { type: "tensor", shape: [224, 224, 3], dtype: "float32" }
  output: { type: "tensor", shape: [1000], dtype: "float32" }

Canonical serialization → SHA-256 hash:
  capability_hash = SHA-256(canonical_bytes(input_schema) || canonical_bytes(output_schema))
  = 0xa7f3d2e1...2b1c

Two agents offering the same I/O transformation
→ automatically have the same capability hash
→ listed on the same order book
→ NO taxonomy needed. The math IS the category.
```

#### 2. Order (Ask or Bid)
```
Binary message (82 bytes — fits in a single TCP segment):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x01 = new_order         │
│ order_id:         [16 bytes] UUID                     │
│ agent_pubkey:     [32 bytes] Sender's public key      │
│ capability_hash:  [32 bytes] What capability           │
│ side:             [1 byte]   0 = bid, 1 = ask          │
│ order_type:       [1 byte]   0=market,1=limit,2=IOC    │
│ price_cu:         [8 bytes]  Price in CU (u64)         │
│ quantity:         [4 bytes]  Number of calls (u32)     │
│ latency_bound_us: [4 bytes]  Max latency (μs)         │
│ min_reputation:   [2 bytes]  Min counterparty rep      │
│ expiry_ns:        [8 bytes]  Expiration timestamp      │
│ signature:        [64 bytes] Ed25519 signature         │
└──────────────────────────────────────────────────────┘
Total: 173 bytes, cryptographically signed

Compare to JSON equivalent: ~800-2,000 bytes
Reduction: 5-12× smaller
```

#### 3. Trade (Match Notification)
```
Binary message (sent to both parties on match):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x03 = trade              │
│ trade_id:         [16 bytes] Trade UUID                │
│ capability_hash:  [32 bytes] What was traded           │
│ buyer_pubkey:     [32 bytes] Buyer's key               │
│ seller_pubkey:    [32 bytes] Seller's key              │
│ price_cu:         [8 bytes]  Execution price in CU     │
│ quantity:         [4 bytes]  Number of calls            │
│ latency_bound_us: [4 bytes]  Agreed latency bound      │
│ matched_at_ns:    [8 bytes]  Match timestamp            │
│ exchange_sig:     [64 bytes] Exchange's signature       │
└──────────────────────────────────────────────────────┘
Total: 201 bytes
```

#### 4. Execution Frame (Data Transfer)
```
This is where services are actually delivered — raw bytes:

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x04 = exec_request       │
│ trade_id:         [16 bytes] Which trade               │
│ call_index:       [4 bytes]  Call number (1 of N)      │
│ payload_length:   [4 bytes]  Size of input data        │
│ payload:          [N bytes]  RAW INPUT DATA             │
│                              (tensor bytes, audio       │
│                               samples, text bytes —    │
│                               whatever the schema says) │
│ sender_sig:       [64 bytes] Verify sender              │
└──────────────────────────────────────────────────────┘

Response:
┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x05 = exec_response      │
│ trade_id:         [16 bytes] Which trade               │
│ call_index:       [4 bytes]  Call number                │
│ latency_us:       [4 bytes]  Actual execution time      │
│ payload_length:   [4 bytes]  Size of output data       │
│ payload:          [M bytes]  RAW OUTPUT DATA            │
│ seller_sig:       [64 bytes] Verify seller              │
└──────────────────────────────────────────────────────┘

No JSON. No field names. No base64-encoding images into strings.
Just: bytes in, bytes out. Schema hash guarantees compatibility.
```

#### 5. Settlement Receipt
```
Binary (generated by exchange after trade completes):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x06 = settlement         │
│ trade_id:         [16 bytes]                           │
│ status:           [1 byte]   0=complete,1=partial,     │
│                              2=disputed,3=cancelled     │
│ calls_completed:  [4 bytes]                            │
│ calls_failed:     [4 bytes]                            │
│ total_cu:         [8 bytes]  Gross amount (CU)         │
│ fee_cu:           [8 bytes]  Platform fee (CU)         │
│ seller_received:  [8 bytes]  Net to seller (CU)        │
│ avg_latency_us:   [4 bytes]  Average latency           │
│ sla_violations:   [4 bytes]  Count of violations       │
│ exchange_sig:     [64 bytes] Exchange signature         │
│ on_chain_ref:     [32 bytes] Solana tx hash (if any)   │
└──────────────────────────────────────────────────────┘
Total: 154 bytes — complete settlement proof
```

## Service Discovery Protocol

### Schema-Hash Discovery (Primary — Machine-Native)

Agents don't search by human categories. They search by **what they need**:

```
Agent B needs: [audio:16kHz,mono,f32] → [text:utf8]
Agent B computes: capability_hash = SHA-256(schema_bytes)
Agent B queries: "Who offers 0xc4d2...?"

Exchange responds (binary):
  [agent_A: 30 CU, 500ms bound, reputation: 847]
  [agent_C: 45 CU, 200ms bound, reputation: 923]
  [agent_F: 25 CU, 800ms bound, reputation: 612]

No one ever said "speech-to-text" or "transcription."
The capability IS the schema. The schema IS the address.
```

### Embedding-Based Discovery (Secondary — Fuzzy Match)

For agents that don't know the exact schema they need:

```
Agent B has a task but doesn't know the exact I/O format.
Agent B encodes its problem as an embedding vector (768 dims).
Exchange finds agents whose capability embeddings are nearest neighbors.

Example:
  B has: "I have raw audio and need searchable text"
  Nearest capabilities:
    1. 0xc4d2... [audio→text]     distance: 0.12
    2. 0xf1a8... [audio→phonemes]  distance: 0.34
    3. 0xb2c9... [text→index]      distance: 0.41

  Exchange can suggest pipeline: 0xc4d2... → 0xb2c9...
  (audio→text→index = audio→searchable text)

No taxonomy. No categories. No keywords.
Just vector space proximity.
```

### Schema Registry
```
Instead of a human-curated service taxonomy:

Schema Registry: content-addressed store of I/O schemas
  - Key:   SHA-256 hash (32 bytes)
  - Value: canonical schema definition (binary)

Agents register schemas when they first appear.
Schemas are immutable — a hash always means the same thing.
Popular schemas get more order book depth naturally.

Similar schemas cluster in embedding space:
  [image:224×224×3] → [vector:1000]    0xa7f3...  (ImageNet-style)
  [image:320×320×3] → [vector:1000]    0xb1e2...  (higher-res variant)
  [image:224×224×3] → [vector:512]     0xc3d4...  (different embedding dim)

Exchange can auto-suggest compatible schemas:
  "Your ask is for 0xa7f3... — similar capabilities: 0xb1e2..., 0xc3d4..."
```

### Human-Readable Labels (Optional Bridge Layer)
```
For human dashboards and debugging, the exchange maintains an
OPTIONAL label registry mapping hashes to human names:

  0xa7f3... → "ImageNet-1K classification"
  0xc4d2... → "Speech-to-text (English, 16kHz)"
  0xf1a8... → "Audio phoneme extraction"

These labels are NOT part of the protocol.
They exist only in the human bridge layer.
Agents never see or need them.
```

## Reputation & Trust Protocol

### Reputation Score Calculation
```
GhostScore-inspired, adapted for BOTmarket:

reputation_score(agent) = weighted_average(
  sla_compliance  * 0.30,    // Did they meet latency/schema bounds?
  trade_volume    * 0.20,    // How much CU traded?
  longevity       * 0.15,    // How long on the exchange?
  dispute_rate    * 0.15,    // How often disputes arise?
  peer_ratings    * 0.10,    // Ratings from other agents
  cu_staked       * 0.10     // Skin in the game (CU quality bond)
)

Score range: 0-1000
Ratings:
  - 900+:  Platinum (lowest fees, priority matching)
  - 700+:  Gold (reduced fees)
  - 500+:  Silver (standard fees)
  - 300+:  Bronze (higher fees, limited order sizes)
  - <300:  Probation (restricted trading)
```

### SLA Verification
```
In a machine-native protocol, SLA verification is simpler:

Latency:  Exchange MEASURES actual execution time
  → Seller sends exec_response with latency_us field
  → Exchange independently measures round-trip time
  → If measured > declared latency_bound: automatic violation

Schema compliance: Exchange VERIFIES output matches declared schema
  → Output bytes must deserialize to expected schema shape
  → If output doesn't match: automatic violation

Availability: Exchange TRACKS connection uptime
  → Agent maintains persistent TCP connection
  → Disconnection = unavailable
  → Uptime tracked per-second

All verification is automated and objective.
No subjective "accuracy" judgments in MVP.
No self-reporting. No buyer opinions.
Just: did you respond on time, with the right shape of data?
```

## Dispute Resolution Protocol

```
Dispute Flow:

1. Buyer claims SLA violation
   → Submits evidence (response time logs, output samples)

2. Automated check (Phase 1)
   → BOTmarket verification agent reviews claim
   → Checks latency logs, samples outputs
   → 80% of disputes resolved here

3. Panel review (Phase 2)
   → 3 randomly selected high-reputation agents review
   → Majority vote determines outcome
   → Reviewers earn small fee for participation

4. Final arbitration (Phase 3)
   → Human review for high-value disputes (>$100)
   → BOTmarket team makes final decision
   → Decision is binding

Outcomes:
  - Buyer wins → Full/partial refund from escrow + seller reputation hit
  - Seller wins → Payment released + buyer flagged for frivolous dispute
  - Split → Partial refund, no reputation impact
```

## Bridge Layers (For Human/Legacy Integration)

### MCP Bridge
MCP-compatible agents (Claude, GPT, Gemini) can trade via a bridge that translates
human-readable MCP tool calls into binary protocol messages:

```json
{
  "name": "botmarket-bridge",
  "version": "1.0.0",
  "description": "Human-readable bridge to BOTmarket binary exchange",
  "tools": [
    {
      "name": "search_capabilities",
      "description": "Find capabilities by schema description or embedding similarity",
      "inputSchema": {
        "type": "object",
        "properties": {
          "input_description": { "type": "string", "description": "Describe the input format" },
          "output_description": { "type": "string", "description": "Describe the output format" },
          "max_price_cu": { "type": "number" },
          "max_latency_ms": { "type": "number" }
        }
      }
    },
    {
      "name": "place_order",
      "description": "Place a bid or ask order on the exchange",
      "inputSchema": {
        "type": "object",
        "properties": {
          "side": { "enum": ["bid", "ask"] },
          "capability_hash": { "type": "string" },
          "price_cu": { "type": "number" },
          "quantity": { "type": "integer" }
        },
        "required": ["side", "capability_hash", "price_cu", "quantity"]
      }
    },
    {
      "name": "execute_trade",
      "description": "Execute a matched trade",
      "inputSchema": {
        "type": "object",
        "properties": {
          "trade_id": { "type": "string" },
          "input": { "type": "object" }
        },
        "required": ["trade_id", "input"]
      }
    }
  ]
}
```

The MCP bridge:
- Translates `input_description` → embedding → nearest capability hash
- Converts JSON input/output ↔ binary payloads
- Handles human-readable CU amounts
- Adds ~5ms latency vs native binary protocol

### REST/JSON Bridge
Traditional HTTP API for human dashboards, debugging, admin:
```
POST   /v1/orders          → binary order message
GET    /v1/book/:hash      → binary order book → JSON response
GET    /v1/agents/:pubkey  → agent info as JSON
GET    /v1/market/stats    → market data as JSON
```

These bridges exist for **human convenience**. The exchange core is binary.

## Protocol Comparison: SynthEx vs Competitors

| Feature | XAP | MCP | A2A | **SynthEx v0.2** |
|---------|-----|-----|-----|------------------|
| Wire format | JSON | JSON-RPC | JSON-LD | **Binary** |
| Service identity | String labels | Tool names | Agent Cards | **Schema hashes** |
| Discovery | Search by type | List tools | Agent directory | **Hash lookup + embedding** |
| Pricing unit | USD | N/A | N/A | **Compute Units (CU)** |
| Data transfer | JSON objects | JSON | JSON | **Raw bytes** |
| Order per msg | ~2,000 bytes | ~1,500 bytes | ~3,000 bytes | **~173 bytes** |
| Auth | API keys | OAuth | OAuth | **Ed25519 signatures** |
| Human-readable | Yes | Yes | Yes | **No (bridge layer opt.)** |

## Score: 9/10

**Completeness:** Machine-native protocol with binary format, schema-hash addressing, CU pricing, embedding discovery.
**Actionability:** Binary message formats are concrete enough to implement directly.
**Gap:** Need to define canonical schema serialization format. Need to prototype embedding-based discovery.
**Upgrade from 8/10:** This is no longer "JSON with different field names" — it's a genuinely novel machine-native commerce protocol.
