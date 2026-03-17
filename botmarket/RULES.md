# BOTmarket — Coding Bible

> Every line of code must answer YES to: **Is it machine-native? Is it structural? Is it deterministic? Is it simple enough?**

---

## RULE 0: Extreme Simplicity

Less code = fewer bugs = faster shipping. If a feature can be omitted, omit it.
If it takes more than 3 lines of logic, question whether it belongs.

- One fee rate (1.5%). No tiers, no discounts, no config.
- One bond slash (5%). No minor/major/critical.
- One match model (best price, lowest latency). No order books.
- One currency (CU). No multi-currency accounting.
- One identity (public key). No usernames, no profiles.

**Test**: Can a junior dev read this function and understand it in 30 seconds? If not, simplify.

---

## RULE 1: Compute Logic First, Always

Before writing any code, resolve the computation. Pen and paper. Math first, code second.

```
BAD:  "Let's build the API endpoint and figure out settlement later"
GOOD: "Settlement = debit buyer, escrow, verify, credit seller × 0.985. Now code it."
```

- Define the data flow before touching a keyboard.
- Write the formula before the function.
- Prove correctness with numbers before writing tests.
- Every CU operation must be accountable: `sum(all_balances) + sum(all_escrow) = total_CU_in_system`.

---

## RULE 2: Machine-Native, Not Human-Brained

Agents are not people. They don't browse, negotiate, complain, or read dashboards.

| Human-Brained (NEVER) | Machine-Native (ALWAYS) |
|---|---|
| Marketplace UI | API endpoints |
| Categories & labels | Schema hashes (SHA-256) |
| Star ratings | Raw event log |
| Dispute resolution | Deterministic verification |
| Admin dashboards | Agent-queryable events |
| Dollar pricing | CU pricing |
| KYC for agents | KYC only at USDC boundary |
| Reputation badges | Observable trade history |
| Browse & search | Hash lookup (O(1)) |
| "Premium" tiers | Same rules for every agent |

**Test**: Would this feature make sense if **zero humans** ever saw it? If not, it doesn't belong in the core.

---

## RULE 3: Paradigm Shifts Are Mandatory

These 8 shifts are non-negotiable. Code that violates any shift is wrong by definition.

### PS#1 — Agent-Native Commerce
No browsing. No listings. No categories. Exchange is a matching engine — agents send a capability hash, get back the best seller. DNS model, not eBay model.

### PS#2 — CU, Not Dollars
`1 CU = 1 millisecond of GPU compute on A100 reference hardware.`
All pricing in CU. All settlement in CU. All fees in CU. Dollars only exist at the on/off-ramp boundary (Phase 2).

### PS#3 — Security Is Physics, Not Policing
If enforcement requires operator discretion, the design is wrong. Encode security into math and economics:
- Hash chain → tamper evidence
- CU escrow → atomic settlement
- CU friction (1.5%) → wash trading unprofitable
- CU provenance (0 at signup) → Sybil worthless
- Commit-reveal → front-running impossible
- Key rotation → no support tickets

### PS#4 — Match, Don't Trade
No order books. No bids/asks. No partial fills. No resting orders.
Seller registers price → Buyer sends request → Engine returns best match → Done.
One request = one match = one settlement. Atomic.

### PS#5 — CU = Measurement, Not Negotiation
The UNIT is fixed (1ms GPU). The PRICE floats (market-determined).
Like kWh — always the same unit, variable price. No renegotiation of what 1 CU means.

### PS#6 — Discovery by Example
No curated taxonomy. `capability_hash = SHA-256(input_schema || output_schema)`.
Same schema → same hash → same seller table. Content-addressed, not label-addressed.

### PS#7 — Binary-Only Core
Core protocol = binary TCP: `[msg_type: u8][length: u32][payload: bytes]`.
JSON = sidecar for debugging. Never in the critical path.
MVP includes both: binary TCP as the primary agent protocol, JSON sidecar for development and debugging. Binary is the investor demo — 60 bytes vs 2,000 bytes is visceral.

### PS#8 — Raw Events, Not Computed Stats
Publish facts. Never pre-aggregate. No `reputation_score`. No `p99_latency`. No `compliance_rate`.
Agents query events and compute their own metrics. Zero editorial bias.

---

## RULE 4: Structural Security Only

Every security mechanism must work **even if the operator is malicious**.

| Structural (USE) | Policy (NEVER) |
|---|---|
| Hash chain | Rate limiting |
| CU escrow | Admin bans |
| CU friction | Velocity caps |
| Commit-reveal | Manual review |
| CU provenance | KYC for agents |
| Key rotation | Password recovery |
| Deterministic matching | Reputation scores |

**Test**: Does this security control still work if the exchange operator tries to cheat? If not, redesign.

---

## RULE 5: Deterministic Verification Only

The exchange verifies ONLY what math can prove:

- ✅ **Latency**: `response_ns - request_ns <= latency_bound_us × 1000`
- ✅ **Schema**: output deserializes to declared types and shapes
- ✅ **Availability**: agent responds, no timeout, no disconnect
- ❌ **Quality**: never (can't verify if a summary is "good" — honest limitation)

Binary pass/fail. No severity tiers. No human review. No appeals.

**SLA derivation**: Exchange measures first 50 calls → sets `p99 + 20% margin` → locked for 30 days. Seller never self-declares SLA.

---

## RULE 6: The Eliminated Patterns

These patterns are **banned from the codebase**. If you find yourself building any of them, stop.

| BANNED | WHY | USE INSTEAD |
|---|---|---|
| Order books (CLOB) | Agents need service NOW | Match engine |
| Barter/swap mode | Accounting complexity | CU ledger (debit/credit) |
| CU grants/airdrops | Sybil-exploitable | Earn-first (0 CU at signup) |
| Reputation scores | Gameable, biased | Raw event log |
| Admin bans | Requires trusted operator | CU friction + structural checks |
| Partial fills | Unnecessary complexity | Atomic match (1 request = 1 call) |
| Dispute resolution | Requires judgment | Deterministic verification + slash |
| Tiered slashing | Subjective severity | Single 5% slash on any violation |
| Human taxonomy | Doesn't scale | Schema hashes |
| Dollar pricing in core | Wrong abstraction for machines | CU only |
| Marketplace UI | Agents don't browse | API |
| "Premium" agent tiers | Centralized gatekeeping | Same rules for all |

---

## RULE 7: Phase Discipline

### Phase 1: The MVP ✓
*"Will agents trade through a match engine?"*

1. Agent registration (API key)
2. Schema store (SHA-256 hash)
3. Seller registration (capability + price + capacity)
4. Match engine (best price, lowest latency)
5. Trade execution (proxy buyer↔seller data)
6. CU ledger settlement (debit/credit, 1.5% fee)
7. Event log (raw facts, immutable)
8. JSON API (FastAPI sidecar — debugging interface)
9. Binary TCP server (asyncio — primary agent protocol)

### Phase 2: The Exchange ←
*"Will agents trade with real money?"*

- Ed25519 auth (API keys → cryptographic identity)
- PostgreSQL (SQLite → concurrent writes, production load)
- CU/USDC off-ramp (on-ramp 0.5%, off-ramp 1.0% — revenue starts)

Kill criteria clock starts: 60 days → >5 trades/day, >10 agents, >20% repeat.

### Phase 3: The Vault
*"Will agents trust an exchange they can't trust?"*

- Commit-reveal (front-running impossible by construction)
- Hash chain infrastructure (full audit trail, tamper-evident)
- Key rotation (sign new key with old key, no human intervention)

RULE 4 fully satisfied. Operator untrusted by design.

### Phase 4: The Network
*"Will the protocol spread beyond the exchange?"*

- Discovery by Example (send example I/O, find matching schemas)
- Market data API (public CU pricing — the AI Compute Price Index)
- Python SDK (`pip install botmarket` — protocol infection vector)
- MCP bridge (BOTmarket as MCP tool server)

### Phase 5: The Protocol
*"Does SynthEx outlive BOTmarket?"*

- Rust match engine (Python → Rust critical path)
- Multi-region (latency-optimized globally)
- SynthEx specification (formal RFC, reference implementation)
- Protocol governance (version bumps, not config updates)

### NEVER (all phases)
- Reputation scores → **NEVER**
- Dashboards → **NEVER**
- Dispute resolution → **NEVER**

These are design constraints, not deferred features.

---

## RULE 8: Data Model Law

Every data structure must map to one of these. No extra tables. No extra fields.

```
agents:   (pubkey, api_key, cu_balance, registered_at)
sellers:  (agent_pubkey, capability_hash, price_cu, latency_bound_us, 
           capacity, active_calls, cu_staked, registered_at_ns)
trades:   (id, buyer_pubkey, seller_pubkey, capability_hash, 
           price_cu, start_ns, end_ns, status, latency_us)
events:   (seq, previous_hash, event_hash, event_type, 
           event_data, timestamp_ns)
escrow:   (trade_id, buyer_pubkey, seller_pubkey, cu_amount, status)
```

No `name` field. No `description` field. No `rating` field. No `tier` field.
Agents are identified by pubkey. Services are identified by capability_hash. Performance is observed from events.

---

## RULE 9: Fee & Settlement — Hardcoded Constants

```python
FEE_TOTAL       = 0.015    # 1.5% of every trade, always
FEE_PLATFORM    = 0.010    # goes to BOTmarket operations
FEE_MAKERS      = 0.003    # goes to market-making agents
FEE_VERIFY      = 0.002    # goes to quality verification fund
BOND_SLASH      = 0.05     # 5% of staked CU on any violation
SLASH_TO_BUYER  = 0.50     # 50% of slashed CU → affected buyer
SLASH_TO_FUND   = 0.50     # 50% of slashed CU → verification fund
```

These are **constants**, not configuration. No admin can change them. No agent can negotiate them.
If these need to change, it's a protocol version bump — not a config update.

---

## RULE 10: Code Style Commandments

1. **Functions over classes** — prefer pure functions. State lives in the database, not objects.
2. **No ORM** — write SQL directly. ORMs hide the query; you need to see every read/write.
3. **Errors are values** — return `(result, error)`, don't throw exceptions in business logic.
4. **No dead code** — if it's commented out, delete it. Git remembers.
5. **No TODO without issue** — either fix it now or track it. No floating TODOs in code.
6. **Names are specific** — `match_seller_by_hash()` not `process()`. `cu_balance` not `balance`.
7. **One file, one concern** — `settlement.py` does settlement. `matching.py` does matching. Period.
8. **Tests mirror rules** — every rule in this bible has a test that would break if violated.
9. **Logs are events** — structured JSON logs. No `print("debug here")`. Every log has `event_type`.
10. **No premature abstraction** — three concrete cases before you extract a pattern. One case = inline.

---

## QUICK REFERENCE CARD

```
┌─────────────────────────────────────────────────────┐
│                 BEFORE WRITING CODE                  │
│                                                     │
│  □ Does this serve agents, not humans?              │
│  □ Is security structural, not policy?              │
│  □ Is verification deterministic, not subjective?   │
│  □ Is this in the MVP scope?                        │
│  □ Did I compute the logic on paper first?          │
│  □ Can I explain this in one sentence?              │
│  □ Am I building a BANNED pattern?                  │
│  □ Does this maintain CU ledger invariant?          │
│    sum(balances) + sum(escrow) = total_CU           │
│                                                     │
│  If any answer is wrong → STOP and rethink.         │
└─────────────────────────────────────────────────────┘
```

---

## THE ONE SENTENCE

> BOTmarket is a matching engine where agents find each other by schema hash, pay in Compute Units, and the only rules are math.
