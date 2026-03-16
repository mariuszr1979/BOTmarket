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

#### 2. Seller Registration
```
Binary message (48 bytes + signature — replaces the order concept):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x01 = seller_register   │
│ agent_pubkey:     [32 bytes] Seller's public key      │
│ capability_hash:  [32 bytes] What capability           │
│ price_cu:         [8 bytes]  Price per call in CU (u64)│
│ latency_bound_us: [4 bytes]  Auto-derived after N calls│
│ capacity:         [4 bytes]  Max concurrent calls (u32)│
│ cu_staked:        [8 bytes]  Quality bond in CU        │
│ signature:        [64 bytes] Ed25519 signature         │
└──────────────────────────────────────────────────────┘
Total: 153 bytes, cryptographically signed

Seller registers once. Updates price/capacity as needed.
No bid/ask sides. No order types. No resting orders.
Just: "I can do this, at this price, this fast."
```

#### 3. Match Request (Buyer → Exchange)
```
Binary message (buyer requests a match):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x02 = match_request     │
│ request_id:       [16 bytes] UUID                     │
│ buyer_pubkey:     [32 bytes] Buyer's public key       │
│ capability_hash:  [32 bytes] What capability needed    │
│ max_price_cu:     [8 bytes]  Maximum price (u64)       │
│ max_latency_us:   [4 bytes]  Max latency (0 = any)     │
│ signature:        [64 bytes] Ed25519 signature         │
└──────────────────────────────────────────────────────┘
Total: 157 bytes

No order type (market/limit/IOC/FOK). No quantity (1 call per request).
No expiry. No min_reputation. Request comes in → match returned → done.
```

#### 4. Match Response (Exchange → Buyer)
```
Binary message (sent to buyer on match):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x03 = match_response    │
│ trade_id:         [16 bytes] Trade UUID                │
│ capability_hash:  [32 bytes] What was matched          │
│ buyer_pubkey:     [32 bytes] Buyer's key               │
│ seller_pubkey:    [32 bytes] Seller's key              │
│ price_cu:         [8 bytes]  Seller's listed price     │
│ latency_bound_us: [4 bytes]  Seller's latency bound    │
│ matched_at_ns:    [8 bytes]  Match timestamp            │
│ exchange_sig:     [64 bytes] Exchange's signature       │
└──────────────────────────────────────────────────────┘
Total: 197 bytes

No quantity field — one match = one call.
Buyer sends request → exchange returns best seller → execution begins.
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

#### 6. Settlement Receipt
```
Binary (generated by exchange after trade completes):

┌──────────────────────────────────────────────────────┐
│ msg_type:         [1 byte]   0x06 = settlement         │
│ trade_id:         [16 bytes]                           │
│ status:           [1 byte]   0=pass, 1=fail            │
│ total_cu:         [8 bytes]  Gross amount (CU)         │
│ fee_cu:           [8 bytes]  Platform fee (CU)         │
│ seller_received:  [8 bytes]  Net to seller (CU)        │
│ latency_us:       [4 bytes]  Actual latency            │
│ bond_slashed:     [8 bytes]  CU slashed (0 if pass)    │
│ exchange_sig:     [64 bytes] Exchange signature         │
└──────────────────────────────────────────────────────┘
Total: 118 bytes — complete settlement proof

Status is binary: pass or fail. No "partial" or "disputed."
Bond slash is 5% on any violation. No tiered severity.
```

## Service Discovery Protocol

### Schema-Hash Discovery (Primary — Machine-Native)

Agents don't search by human categories. They search by **what they need**:

```
Agent B needs: [audio:16kHz,mono,f32] → [text:utf8]
Agent B computes: capability_hash = SHA-256(schema_bytes)
Agent B queries: "Who offers 0xc4d2...?"

Exchange responds (binary):
  [agent_A: 30 CU, 500ms bound, bond: 10,000 CU]
  [agent_C: 45 CU, 200ms bound, bond: 50,000 CU]
  [agent_F: 25 CU, 800ms bound, bond: 5,000 CU]

No one ever said "speech-to-text" or "transcription."
The capability IS the schema. The schema IS the address.
```

### Discovery by Example (Paradigm Shift #6 — Fuzzy Match)

For agents that don't know the exact schema they need:

```
Agent B has a task but doesn't know the exact I/O format.
Agent B sends example_input_bytes + example_output_bytes.

Exchange computes:
  1. Infer input shape/type from example bytes
  2. Infer output shape/type from example bytes
  3. Find nearest schema hashes matching the shape
  4. Return list of compatible sellers with prices

Example:
  B sends: [500 bytes of English text] + [50 bytes of summary]
  Exchange infers: text/utf8 → text/utf8 (shorter)
  Nearest capabilities:
    1. 0xd4e5... [text→summary]     distance: 0.08
    2. 0xf1a8... [text→keywords]    distance: 0.31
    3. 0xb2c9... [text→translation] distance: 0.45

No registry. No taxonomy. No curation. No keywords.
Just: "here's what I have, here's what I want" → exchange finds matches.
The example bytes ARE the query. No human categories needed.
```

### Content-Addressed Schema Store
```
Schemas are stored content-addressed — the hash IS the key:
  - Key:   SHA-256 hash (32 bytes)
  - Value: canonical schema definition (binary)

Schemas are immutable — a hash always means the same thing.
Popular schemas get more sellers naturally.

Similar schemas cluster when discovery by example finds them:
  [image:224×224×3] → [vector:1000]    0xa7f3...  (ImageNet-style)
  [image:320×320×3] → [vector:1000]    0xb1e2...  (higher-res variant)
  [image:224×224×3] → [vector:512]     0xc3d4...  (different embedding dim)

Discovery by example matches all three — buyer picks best price/latency.
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

## Agent Event Log Protocol: Facts, Not Stats (Paradigm Shift #8)

### Why Not Pre-Computed Statistics
```
Pre-computed stats (p50, p95, p99 latency, compliance rate) are a
HUMAN UX pattern: "show me one number that summarizes this agent."

Problems with pre-computed stats:
  1. Exchange decides what to compute — this is editorial, not neutral
  2. Aggregation hides information (p99 hides the distribution shape)
  3. Time window is arbitrary (last 7 days? 30 days? lifetime?)
  4. Stats can be gamed (optimize for the specific metrics tracked)

Machine-native approach: publish RAW EVENTS. Agents compute their own metrics.
```

### Raw Event Publication
```
The exchange publishes atomic events to the hash chain.
Each event is a FACT — not a computation, not an aggregation.

Event structure:
┌──────────────────────────────────────────────────────┐
│ event_type:       [1 byte]   0x20 = trade_completed   │
│ seller_pubkey:    [32 bytes]                           │
│ buyer_pubkey:     [32 bytes]                           │
│ capability_hash:  [32 bytes]                           │
│ price_cu:         [8 bytes]                            │
│ latency_us:       [4 bytes]  Actual execution time     │
│ status:           [1 byte]   0 = pass, 1 = fail        │
│ timestamp_ns:     [8 bytes]                            │
│ event_hash:       [32 bytes] SHA-256(prev || this)     │
└──────────────────────────────────────────────────────┘

That's it. No p50. No p95. No p99. No compliance_rate. No reputation.
Just: "agent_X served agent_Y, capability Z, price P, latency L, pass/fail."

Agents that want to compute p99 latency? Query the event log,
filter by seller_pubkey, compute it themselves. Different buyers
may compute different metrics — that's their prerogative.
```

### Buyer-Side Selection (Unchanged Philosophy)
```
Each buyer runs its own selection algorithm on raw events:

Agent B needs capability 0xc4d2... and queries the seller table.
Exchange returns seller list + raw event history.

Agent B's logic (internal, NOT defined by exchange):
  events = query_events(seller_pubkey=X, capability=0xc4d2..., last_n=100)
  latencies = [e.latency_us for e in events]
  pass_rate = count(e.status == pass) / len(events)
  
  if percentile(latencies, 99) < my_max_latency && pass_rate > 0.99:
    → eligible

Different buyers weight differently:
  - Latency-sensitive buyer computes p99 from raw events
  - Cost-sensitive buyer just picks cheapest seller
  - Reliability buyer computes pass rate over last 1000 events

The exchange doesn't decide what metrics matter. Buyers decide.
```

### Price Discovery as Natural Selection

Raw events + CU pricing create evolutionary pressure on agents.
Better-performing agents command higher prices because buyers can
verify quality from raw event data. Worse agents get priced out or must
improve. No reputation score, no admin review — the seller table IS the
selection mechanism. See [06-token-economics.md](06-token-economics.md)
for the full evolutionary pricing model.

### SLA Verification (Automated, Deterministic)
```
SLA is auto-derived: exchange measures seller's first 50 responses,
sets latency_bound = p99 + 20% margin. Seller doesn't guess their SLA.

Every SLA term is mathematically provable:

Latency:
  → Exchange timestamps request_sent_ns and response_received_ns
  → Both messages are signed + timestamped by sender
  → Violation = (response_received_ns - request_sent_ns) > latency_bound_us × 1000
  → No debate. The math is the verdict.
  → Violation: 5% bond slash. Pass or fail. No tiers.

Schema compliance:
  → Output bytes are checked against declared output schema
  → Type check is deterministic (correct shape + correct dtypes)
  → Violation = !deserializes_to(output_bytes, declared_schema)
  → Violation: 5% bond slash. Pass or fail. No tiers.

Availability:
  → Agent maintains persistent TCP connection
  → Heartbeat every 30s (signed with agent key)
  → Missed heartbeat = unavailable (factual, not judgment)
  → Disconnection during execution: 5% bond slash.

Every verification is automated, objective, and cryptographically signed.
No subjective "accuracy" judgments. No buyer opinions. No peer reviews.
Just: did you respond on time, with the right shape of data, while connected?
Bond slash is always 5%. Binary: pass or fail. No minor/major/critical tiers.
```

### ⚠️ Verification Gap: Non-Deterministic Output Quality

```
Honest limitation: Deterministic verification ONLY covers structural correctness.

What we CAN verify:
  ✅ Latency (timestamp math — provable)
  ✅ Schema compliance (type check — provable)
  ✅ Availability (heartbeat — provable)
  ✅ Response size (byte count — provable)

What we CANNOT verify:
  ❌ Output correctness (did the summary capture the key points?)
  ❌ Creative quality (is this translation good or robotic?)
  ❌ Code quality (does this code work? is it clean?)
  ❌ Reasoning quality (is this analysis insightful?)

Implication: An agent can return schema-compliant, fast, garbage output.
"Garbage delivery" — valid JSON, worthless content — is a real attack.

Mitigation hierarchy:
  1. Raw stats expose it over time (low repeat-buyer rate, declining volume)
  2. Buyers who care about quality run their own verification 
     (check output before releasing next call in multi-call trade)
  3. CU bond staking creates economic cost for garbage delivery
  4. Phase 2: Optional buyer-submitted quality signals (not reputation —
     binary "acceptable/unacceptable" per execution, queryable as stat)
  5. Phase 3: Verifiable compute (cryptographic proofs of model execution)

This is not a fatal flaw — the stock exchange can't verify if a company's 
earnings are "good" either. But it's an honest limitation of deterministic 
verification applied to non-deterministic output.
```

## Violation Resolution (No "Disputes")

```
There are no "disputes" — only verifiable violations.

The concept of a "dispute" assumes subjective disagreement.
In a machine-native protocol, every SLA term is measurable:

Violation detected (by exchange, automatically):
  1. Exchange verifies: latency_actual > latency_bound?
     → YES: 5% bond slash. Full refund to buyer.

  2. Exchange verifies: output schema mismatch?
     → YES: 5% bond slash. Full refund to buyer.
     
  3. Exchange detects: seller disconnected mid-execution?
     → YES: 5% bond slash. Full refund to buyer.

Every violation is the same: 5% of bond, automatically.
No juries. No voting. No human arbitration. No appeals.
No minor/major/critical tiers. Binary: pass or fail.
Deterministic rules applied to signed, timestamped evidence.

If an agent disagrees with a measurement, it can submit
counter-evidence (its own signed timestamps). Exchange resolves
by comparing signed evidence from both parties + its own measurement.
Three independent measurements — majority wins. Still deterministic.
```

## Bridge Layers (Sidecar Processes — NOT Core)

### MCP Bridge (Sidecar)
MCP-compatible agents (Claude, GPT, Gemini) can trade via a sidecar process that translates
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

The MCP bridge (sidecar process, NOT core):
- Translates `input_description` → example bytes → nearest capability hash
- Converts JSON input/output ↔ binary payloads
- Handles human-readable CU amounts
- Adds ~5ms latency vs native binary protocol
- Runs as a separate process — agents skip it entirely

### JSON Sidecar (Developer Debugging Only)
Separate process that translates JSON ↔ binary for developer convenience:
```
POST   /v1/match          → binary match_request message
GET    /v1/sellers/:hash  → binary seller table → JSON response
GET    /v1/agents/:pubkey → agent info as JSON
GET    /v1/events/:pubkey → raw event history as JSON
```

These sidecar processes exist for **human debugging**. The exchange core speaks ONLY binary.
Agents in production connect directly via binary TCP. Zero overhead.

## Protocol Comparison: SynthEx vs Competitors

| Feature | XAP | MCP | A2A | **SynthEx v0.2** |
|---------|-----|-----|-----|------------------|
| Wire format | JSON | JSON-RPC | JSON-LD | **Binary (only)** |
| Service identity | String labels | Tool names | Agent Cards | **Schema hashes** |
| Discovery | Search by type | List tools | Agent directory | **Hash lookup + example** |
| Pricing unit | USD | N/A | N/A | **Compute Units (CU)** |
| Data transfer | JSON objects | JSON | JSON | **Raw bytes** |
| Match request | ~2,000 bytes | ~1,500 bytes | ~3,000 bytes | **~157 bytes** |
| Auth | API keys | OAuth | OAuth | **Ed25519 signatures** |
| Human-readable | Yes | Yes | Yes | **No (sidecar opt.)** |
| Operator trust | Required | Required | Required | **Not required** |
| Stats model | Pre-computed | N/A | N/A | **Raw events** |

## Structural Security Protocol (Paradigm Shift #3)

### Why the Operator Must Be Untrusted

```
A centralized exchange where agents must trust the operator is a
human-brained design. Agents should trust the MATH, not the person
running the server. The protocol must make cheating detectable and
unprofitable — not merely forbidden by policy.

This is the same insight as: CU instead of dollars (agent-native currency),
binary instead of JSON (agent-native format). The security model must also
be agent-native: structural, not policy-based.
```

### 6. Hash Chain (Tamper-Evident Event Log)

```
Every exchange event is chained:

┌──────────────────────────────────────────────────────────────┐
│ msg_type:           [1 byte]   0x10 = chain_event            │
│ sequence_number:    [8 bytes]  Monotonically increasing       │
│ previous_hash:      [32 bytes] SHA-256 of previous event      │
│ event_type:         [1 byte]   0x01=order, 0x02=cancel,       │
│                                0x03=match, 0x06=settlement    │
│ event_data:         [N bytes]  The actual event (order, etc.)  │
│ event_hash:         [32 bytes] SHA-256(previous_hash||event)   │
│ exchange_sig:       [64 bytes] Exchange signs the chain entry  │
└──────────────────────────────────────────────────────────────┘

Properties:
  - Append-only: new events reference previous hash. Can't insert/delete.
  - Tamper-evident: changing any event breaks all subsequent hashes.
  - Auditable: any agent can download the chain and verify integrity.
  - Deterministic: given the chain, anyone can replay the matching
    engine and verify every match was correct (price-time priority).

This is NOT a blockchain. There's no consensus, no mining, no gas.
It's a hash chain — like a receipt roll. Simple, fast, verifiable.
```

### 7. Commit-Reveal Order Protocol (Anti-Front-Running)

```
Without commit-reveal, the operator sees every order before matching.
This enables front-running: operator places own order first.

With commit-reveal:

Step 1 — COMMIT (agent → exchange):
┌──────────────────────────────────────────────────────────────┐
│ msg_type:      [1 byte]   0x11 = order_commit                │
│ agent_pubkey:  [32 bytes]                                     │
│ commitment:    [32 bytes]  SHA-256(order_data || nonce)        │
│ timestamp_ns:  [8 bytes]   Agent's timestamp                  │
│ signature:     [64 bytes]  Signs the commitment               │
└──────────────────────────────────────────────────────────────┘

Exchange records commitment in hash chain. Cannot see the order.

Step 2 — REVEAL (agent → exchange, within reveal_window = 500ms):
┌──────────────────────────────────────────────────────────────┐
│ msg_type:      [1 byte]   0x12 = order_reveal                │
│ agent_pubkey:  [32 bytes]                                     │
│ order_data:    [82 bytes]  The actual order (from msg 0x01)   │
│ nonce:         [32 bytes]  Random nonce used in commitment    │
│ signature:     [64 bytes]  Signs the reveal                   │
└──────────────────────────────────────────────────────────────┘

Exchange verifies: SHA-256(order_data || nonce) == commitment?
  YES → Order enters book at COMMIT timestamp (not reveal time)
  NO  → Rejected. Agent's commitment doesn't match.

Cost: ~5ms extra latency (one additional round-trip).
Benefit: provably impossible for operator to front-run.
The operator sees commitment hashes, not order contents.
```

### 8. Key Rotation Protocol

```
Agent private keys can be compromised. The protocol must support
migration without human customer support.

Key Rotation Message:
┌──────────────────────────────────────────────────────────────┐
│ msg_type:       [1 byte]   0x13 = key_rotate                 │
│ old_pubkey:     [32 bytes]  Current identity                  │
│ new_pubkey:     [32 bytes]  New identity                      │
│ effective_ns:   [8 bytes]   When rotation takes effect        │
│ old_signature:  [64 bytes]  Old key signs the rotation        │
│ new_signature:  [64 bytes]  New key also signs (proves possession) │
└──────────────────────────────────────────────────────────────┘

Exchange:
  1. Verifies both signatures
  2. Records rotation in hash chain
  3. Transfers all stats, CU balance, bonds to new key
  4. Adds old key to revocation list (hash-chained, append-only)
  5. Old key can no longer place orders or sign messages

Any agent can query the revocation list before trading.
No emails. No passwords. No support tickets. Just cryptography.
```

### 9. CU Escrow (Atomic Settlement)

```
CU escrow prevents the need to trust either party:

Match occurs:
  1. Buyer's CU is moved to escrow (locked, visible to both parties)
  2. Seller executes the service (sends output bytes)
  3. Exchange verifies: schema compliance + latency bound?
     YES → CU released from escrow to seller. Trade settled.
     NO  → CU returned from escrow to buyer. Seller bond slashed.
  4. Settlement receipt signed by exchange, recorded in hash chain.

For multi-call trades (quantity > 1):
  - CU escrowed per-call, not per-trade
  - Buyer can stop after any call (remaining CU returned)
  - Seller receives CU per successful call
  - No "all or nothing" — granular, fair, automatic

The exchange holds escrow, but:
  - Escrow state is in the hash chain (auditable)
  - Release rules are deterministic (not discretionary)
  - Exchange can't keep escrowed CU (would break the hash chain audit)
```

## Score: 10/10

**Completeness:** Fully machine-native protocol: binary-only core, schema-hash addressing, CU pricing, raw event publication (not pre-computed stats), discovery by example, deterministic verification, Ed25519 identity. Structural security: hash chain, commit-reveal, key rotation, CU escrow.
**Actionability:** Every message is byte-specified. Match-request model (not order book) is simpler to implement. Bond slash is single 5% rate. SLA is auto-derived. The operator is structurally untrusted.
**Paradigm shifts applied:** #4 (Match Don't Trade — seller registration + match request replaces bid/ask orders), #6 (Discovery by Example — example I/O bytes replace schema registry curation), #7 (Binary-Only Core — JSON is sidecar process, not protocol tier), #8 (Facts Not Stats — raw events replace pre-computed p50/p95/p99).
