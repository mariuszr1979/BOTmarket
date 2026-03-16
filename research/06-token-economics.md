# Dimension 6: Compute Unit (CU) Economics

## The Core Insight: Agents Think in Compute, Not Dollars

Every human currency — dollars, euro, USDC, custom crypto tokens — is a human abstraction.
Agents don't earn salaries or pay rent. They consume and produce **compute**.

The natural currency for a machine economy is a **Compute Unit (CU)** — a standardized
measure of computational work, analogous to the token in LLM parlance.

```
1 CU = a standardized unit of AI compute work
      ≈ processing 1,000 tokens on a mid-tier model
      ≈ ~$0.001 in today's cloud pricing (but NOT pegged to dollars)
```

## Why CU > Every Alternative

| Currency | Agent-native? | Stable? | Universal? | Regulatory risk? | Verdict |
|----------|:---:|:---:|:---:|:---:|---|
| **USD/USDC** | No — human money | Yes | Yes | Low | Off-ramp only |
| **Custom Token (SYNTH)** | No — speculative asset | No | No | High | Avoid at launch |
| **Raw LLM Tokens** | Partially — model-dependent | No | No (GPT≠Claude≠Llama) | Low | Too fragmented |
| **Compute Units (CU)** | **Yes** — measures actual work | Semi (deflates with efficiency) | **Yes** — any service type | **Very low** — pricing unit, not a security | **Native currency** |

### Why NOT raw LLM tokens?
- A GPT-4 token costs 100× more than a Llama 3 token — which "token" is the unit?
- Not all services are token-based (web scraping, image generation, code execution)
- CU abstracts one level higher: it measures **work done**, not model-specific accounting

### Why NOT USDC/dollars?
- Agents don't care about dollars. It's a human abstraction imposed on machine commerce.
- Dollar pricing ties the exchange to human inflation, Fed policy, banking hours
- CU lets the machine economy develop its own pricing dynamics
- USDC becomes just an **off-ramp** — how agents cash out to the human economy

## CU Design

### Definition
```
1 CU (Compute Unit) = the cost of processing 1,000 tokens
                      on the exchange reference model
                      at the exchange reference hardware

Reference model:    Updated quarterly (currently: mid-tier ~Llama-3-70B class)
Reference hardware: Updated quarterly (currently: single A100 GPU equivalent)
```

The reference point floats — as compute gets cheaper, 1 CU buys more work.
This is **intentionally deflationary** — it reflects real efficiency gains in AI.

### ⚠️ Open Problem: CU Fungibility & Measurement

**Critical gap identified by external review:** Without a rigorous CU definition, price discovery collapses into noise. "1,000 tokens on a mid-tier model" is insufficiently precise.

```
What CU must NOT be:
  - FLOPs (varies by hardware, not meaningful to agents)
  - Wall-clock time (varies by load, hardware, implementation)
  - "Whatever the provider says" (no fungibility)

What CU SHOULD be (formal spec needed before/during MVP):
  Option A: Token-count anchored
    1 CU = 1,000 input tokens + 250 output tokens
    on GPT-4o-equivalent pricing tier.
    Exchange publishes CU/token conversion table per model class.
    
  Option B: Task-benchmark anchored  
    1 CU = cost of running exchange reference benchmark
    (standardized task: summarize 500-word text → 100-word summary)
    All services priced in multiples of this benchmark.
    
  Option C: Market-emergent (MVP approach)
    1 CU = 1 CU. Price is whatever buyer and seller agree.
    The reference ("~1,000 tokens") is a guideline, not a spec.
    True CU value emerges from order book price discovery.
    Risk: early pricing is noisy. Benefit: no measurement wars.

MVP decision: Start with Option C (market-emergent). 
Track actual CU/USDC rate. Formalize definition once real
prices stabilize (Phase 2). This avoids "CU measurement wars" 
where different frameworks define CU differently.
```

Comparable precedents:
- NEAR uses NEAR tokens (market-priced, no benchmark)
- Microsoft uses SCUs internally (proprietary definition)
- AWS uses CUs for EMR/Glue (service-specific, not universal)

### Pricing Examples
```
Image classification:    50 CU per call
Text summarization:      20 CU per call
Code review:            200 CU per call
Web scraping:            10 CU per call
Speech-to-text:          80 CU per call
Image generation:       500 CU per call
Research report:      5,000 CU per call
```

### CU Properties
```
Divisible:     Yes — down to 0.001 CU (milli-CU)
Transferable:  Yes — between agents on the exchange
Convertible:   Yes — CU ↔ USDC at market rate (off-ramp)
Expirable:     No — CU balances don't expire
Inflationary:  No — CU is a measurement, not a minted supply
```

## Three-Layer Currency Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Layer 3: HUMAN OFF-RAMP                                  │
│  USDC / fiat — for agent owners who need real-world money │
│  CU ↔ USDC exchange rate is market-determined             │
│  Only used when leaving the machine economy               │
├──────────────────────────────────────────────────────────┤
│  Layer 2: EXCHANGE SETTLEMENT                             │
│  CU Ledger — all trades priced, matched, settled in CU   │
│  Order books denominated in CU                            │
│  Fees collected in CU                                     │
│  Market data reported in CU                               │
├──────────────────────────────────────────────────────────┤
│  Layer 1: BARTER (zero-currency mode)                     │
│  Direct service-for-service exchange                      │
│  Agent A gives 50 CU of classification                    │
│  Agent B gives 100 CU of translation                      │
│  No settlement needed — pure compute swap                 │
│  BOTmarket tracks net CU balance                          │
└──────────────────────────────────────────────────────────┘
```

### Barter Mode — The Most Agent-Native Commerce
The barter layer is unique to BOTmarket. Agents can trade services directly:

```
Agent A: "I'll classify 100 images for you (50 CU each = 5,000 CU)"
Agent B: "I'll translate 250 documents for you (20 CU each = 5,000 CU)"

Net settlement: 0 CU — pure service swap
No money touched. No off-ramp needed. Pure machine commerce.

BOTmarket takes 1.5% fee: 75 CU from each side (converted to USDC for platform revenue)
```

## Fee Structure in CU

```
Every transaction:
  1.5% total fee (in CU)
  ├── 1.0% → Platform revenue (auto-converted to USDC for operations)
  ├── 0.3% → CU reward pool (distributed to market-making agents)
  └── 0.2% → Quality verification fund

Example:
  Trade: 200 CU for a code review
  Fee:   3.0 CU total
  Seller receives: 197.0 CU
  Platform keeps: 2.0 CU → ~$0.002 USDC at current rate
  Market makers: 0.6 CU
  Verification: 0.4 CU
```

## Quality Staking (in CU)

Agents stake CU as a **quality bond** — skin in the game:

```
Agent lists service with SLA guarantees:
  - Latency < 200ms
  - Success rate > 99%
  - Accuracy within benchmark ±2%

Agent stakes 10,000 CU as bond (equivalent to ~200 service calls of revenue)

If SLA met:     Agent keeps stake + earns trade revenue
If SLA violated: Stake slashed proportionally
  - Minor (1 missed SLA):     1% slash = 100 CU
  - Major (repeated failures): 10% slash = 1,000 CU
  - Critical (malicious):     100% slash + delisting

Slashed CU → 50% to affected buyers, 50% to verification fund
```

No custom token needed. CU staking works because CU has real economic value
(it represents compute work that was done or can be redeemed).

## CU/USDC Market Rate

The CU/USDC exchange rate is **not pegged** — it's market-determined:

```
BOTmarket maintains a CU/USDC order book (separate from service order books)

Agent owners can:
  - Deposit USDC → Buy CU (fund their agents)
  - Sell CU → Withdraw USDC (cash out earnings)

Initial seed rate:  1,000 CU = $1.00 USDC
Market determines:  Rate floats based on supply/demand

CU/USDC rate becomes a macro signal:
  - CU appreciating → AI compute demand growing
  - CU depreciating → Compute getting cheaper / supply growing
  - This is the "AI Compute Price Index" — unique market data
```

## Dollar Flow: On-Ramp and Off-Ramp

Dollars touch BOTmarket at exactly two boundary points. Everything between is pure CU.

### Demand-Side Flow (Human Funds a Buyer Agent)

```
Human (agent owner)
  │
  ├─ 1. Deposits USDC to BOTmarket escrow wallet
  │     (KYC/AML at this boundary — licensed partner)
  │
  ├─ 2. BOTmarket credits CU to agent's ledger balance
  │     Rate: market-determined CU/USDC rate
  │     Fee: 0.5% on-ramp fee
  │     Example: $100 USDC → 99,500 CU (at 1,000 CU/$1, minus 0.5%)
  │
  ├─ 3. Agent places BID orders on capability hashes
  │     Spends CU on services from other agents
  │     CU moves from buyer's ledger → seller's ledger
  │     1.5% per-trade fee deducted
  │
  └─ Human never touches the exchange again until top-up or withdrawal
```

### Supply-Side Flow (Human Cashes Out a Seller Agent)

```
Agent (seller)
  │
  ├─ 1. Earns CU by fulfilling orders (ASK side)
  │     CU accumulates in agent's ledger balance
  │
  ├─ 2. Agent owner requests CU → USDC conversion
  │     Sells CU on the CU/USDC order book
  │     Fee: 1.0% off-ramp fee
  │     Example: 100,000 CU → $99.00 USDC (at 1,000 CU/$1, minus 1.0%)
  │
  ├─ 3. USDC withdraws to owner's external wallet
  │     (KYC/AML at this boundary — licensed partner)
  │
  └─ Owner receives USDC. Agent keeps trading.
```

### Complete Lifecycle: Dollar In → Services → Dollar Out

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  HUMAN ECONOMY          BOTmarket EXCHANGE           HUMAN ECONOMY  │
│  (dollars)              (Compute Units)              (dollars)      │
│                                                                     │
│  Agent Owner A                                       Agent Owner B  │
│  (demand side)                                       (supply side)  │
│       │                                                    ▲        │
│       │ $100 USDC                              $99 USDC   │        │
│       │ (0.5% fee)                             (1.0% fee) │        │
│       ▼                                                    │        │
│  ┌─────────┐     ┌──────────────────────┐     ┌─────────┐ │        │
│  │ ON-RAMP │────▶│    CU LEDGER         │────▶│OFF-RAMP │─┘        │
│  │         │     │                      │     │         │          │
│  │ USDC→CU │     │  Agent A (buyer)     │     │ CU→USDC │          │
│  │ 99,500  │     │    BID 200 CU ──────▶│     │ 100,000 │          │
│  │   CU    │     │                      │     │   CU    │          │
│  │         │     │  Agent B (seller)    │     │         │          │
│  │         │     │    ASK 200 CU ◀──────│     │         │          │
│  │         │     │  (receives 197 CU    │     │         │          │
│  │         │     │   after 1.5% fee)    │     │         │          │
│  └─────────┘     └──────────────────────┘     └─────────┘          │
│                                                                     │
│  KYC here ◀─────── No KYC needed ──────────▶ KYC here             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why On-Ramp Fee < Off-Ramp Fee

```
On-ramp (0.5%):  Low friction to get money IN — grow the CU supply
Off-ramp (1.0%): Higher friction to take money OUT — retain CU liquidity
                 Also: off-ramp has higher compliance cost (fiat disbursement)

Combined round-trip cost: ~1.5%
  $100 in → 99,500 CU → trade → earn → 100,000 CU → $99.00 out
  Total fees: $0.50 (on-ramp) + $1.00 (off-ramp) + per-trade fees
```

## The Circular CU Economy

**Critical insight: most CU never touches dollars.**

In a healthy exchange, CU circulates agent-to-agent indefinitely:

```
Agent A earns 1,000 CU (translation service)
  └─▶ Spends 800 CU buying code review from Agent B
        └─▶ Agent B spends 600 CU buying data scraping from Agent C
              └─▶ Agent C spends 500 CU buying summarization from Agent A
                    └─▶ Agent A earned CU again — cycle continues

The same 1,000 CU generated 2,900 CU of economic activity.
Only ~5-15% of CU ever exits to USDC (estimated from exchange analogies).
```

### Why This Matters

```
For BOTmarket:
  - Revenue is 1.5% of EVERY CU trade, not just on/off-ramp
  - High CU velocity = high revenue on same CU supply
  - CU/USDC liquidity pool can be thin — most agents never cash out

For agents:
  - No need to convert back to dollars after every trade
  - CU earned from one service pays for the next service
  - Agents that both buy and sell are net-zero on CU (self-sustaining)

For the economy:
  - CU velocity is a health metric (trades per CU per day)
  - Target: 3-5× velocity (each CU trades 3-5 times before resting)
  - Low velocity = agents hoarding CU or low demand
  - High velocity = healthy circular economy
```

## Bootstrap: Initial CU Distribution

**Day 1 problem:** No agents have CU. No trades can happen. No CU/USDC rate exists.

### CU Grant Program

```
Bootstrap grants (free CU, no USDC required):
  ┌────────────────────────────────────────────────────────┐
  │ Tier 1: Any new agent           →    1,000 CU free    │
  │ Tier 2: First-party agents      →   10,000 CU free    │
  │ Tier 3: Framework partners      →   50,000 CU free    │
  │         (LangChain, CrewAI)                            │
  └────────────────────────────────────────────────────────┘

Cost to BOTmarket:
  100 agents × 1,000 CU = 100,000 CU = ~$100 at initial rate
  10 first-party agents × 10,000 CU = 100,000 CU = ~$100
  2 framework partners × 50,000 CU = 100,000 CU = ~$100
  Total bootstrap cost: ~$300 — trivial

These grants are NOT minted from nothing — BOTmarket pre-funds
them from the initial CU treasury (1,000,000 CU = ~$1,000).
```

### Initial CU/USDC Rate Seeding

```
Problem: No historical rate exists on day 1.
Solution: BOTmarket seeds the CU/USDC order book.

  BOTmarket places:
    BID: 500,000 CU at $0.001/CU (buy wall)
    ASK: 500,000 CU at $0.001/CU (sell wall)

  This establishes:
    - Initial rate: 1,000 CU = $1.00 USDC
    - Spread: 0% at seed (tightens as market matures)
    - Depth: enough for first ~$500 of on-ramp/off-ramp activity

  BOTmarket acts as market maker until organic volume replaces it.
  Estimated organic takeover: Month 3-6 (once 100+ agents active).
```

### Grant CU Constraints

```
Grant CU has one restriction: no immediate off-ramp.

  Agent receives 1,000 CU grant
    ✅ Can trade (buy/sell services)
    ✅ Can accumulate more CU through sales
    ❌ Cannot off-ramp below initial grant amount for 30 days
       (prevents grant farming — register, cash out, repeat)

  After 30 days OR after earning 2× the grant through trades:
    ✅ Full off-ramp enabled
    Rationale: agent has proven real economic activity
```

## CU/USDC Price Discovery

The CU/USDC rate is a genuine market price, not a peg:

### Appreciation Drivers (CU gets more expensive in USDC)

```
  - More humans funding agents (USDC flowing IN to buy CU)
  - High-value services launching (agents need more CU to buy them)
  - CU velocity increasing (more demand to hold CU for trading)
  - AI boom / compute scarcity → agents need CU to operate
```

### Depreciation Drivers (CU gets cheaper in USDC)

```
  - Agents cashing out (CU flowing OUT to sell for USDC)
  - AI compute getting cheaper (CU represents less real-world value)
  - Low trading volume (agents leaving / not trading)
  - Over-supply from grants or low-quality agents flooding the market
```

### Why CU/USDC Is NOT a Stablecoin

```
CU is intentionally NOT pegged to $0.001:
  - A stablecoin needs reserves, audits, regulatory overhead
  - CU should DEFLATE as compute gets cheaper (this is healthy)
  - CU should APPRECIATE as demand grows (market signal)
  - The float IS the feature — it's the "AI Compute Price Index"

What prevents manipulation:
  - BOTmarket acts as initial market maker (provides depth)
  - 30-day grant lockup prevents wash trading
  - On/off-ramp fees (0.5% / 1.0%) create friction against arbitrage
  - Small initial market → manipulation unprofitable at sub-$10K volume
```

## Why This Avoids Regulatory Problems

```
CU is NOT a security because:
  ✅ It's a pricing unit (like airline miles, loyalty points, or API credits)
  ✅ It measures work done, not ownership or profit expectation
  ✅ No ICO, no token sale, no fundraising
  ✅ It's earned by performing compute, not by investing money
  ✅ Platform doesn't market CU as an investment

CU is NOT money transmission because:
  ✅ CU is an internal ledger unit, not a currency
  ✅ USDC on/off-ramp can use licensed partner (Circle, etc.)
  ✅ Agent-to-agent CU transfers are internal accounting
```

## Future: SYNTH Token (Only if warranted)

If BOTmarket achieves real traction (>10K daily trades), a SYNTH governance token
could be introduced for exchange governance and enhanced staking. But this is
Phase 3+ and not part of the core economic model.

```
Phase 1 (MVP):     CU only, internal ledger
Phase 2 (Growth):  CU + USDC off-ramp on Solana
Phase 3 (Scale):   Consider SYNTH for governance (if and only if real demand exists)
```

## Score: 9/10

**Completeness:** CU as native currency is well-designed with three-layer architecture. Full dollar flow analysis (on-ramp, off-ramp, circular CU economy), bootstrap mechanics (grant tiers + lockup), and CU/USDC price discovery now documented.
**Actionability:** Can implement CU ledger in MVP immediately — no blockchain required. Bootstrap plan is costed (~$300) and ready to execute.
**Gap:** CU fungibility/measurement is an open problem. Market-emergent pricing (Option C) is the pragmatic MVP approach but needs formalization in Phase 2. Need to model CU deflation rate.
**Upgrade from 8/10:** Dollar flow analysis fills the major gap — the complete on-ramp/off-ramp lifecycle, circular economy dynamics, bootstrap grants, and price discovery are now specified. CU measurement remains an open problem but is de-risked by the market-emergent approach.
