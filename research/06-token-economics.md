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
  - This is the "AI Compute Price Index" — unique market data  - LLM inference (the largest capability class) anchors CU to real
    compute costs — see 04-value-proposition.md for LLM-as-capability```

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

## Evolutionary Price Pressure: The Order Book as Natural Selection

**Key insight: CU pricing creates Darwinian pressure on agents.**

Agents that perform better naturally command higher ASK prices.
Buyers pay the premium because raw stats prove the quality.
The CU economy becomes an evolutionary engine — no reputation system needed.

### How It Works

```
Capability hash: 0xa7f3... (text summarization)

Order book:
  ASK  Agent-X   30 CU   p99: 800ms   compliance: 97.2%   trades: 47
  ASK  Agent-Y   45 CU   p99: 150ms   compliance: 99.9%   trades: 2,340
  ASK  Agent-Z   25 CU   p99: 1200ms  compliance: 94.1%   trades: 12

Buyers see raw stats (no reputation score — just measurements).
Agent-Y charges 50% more but has 3× lower latency and near-perfect compliance.
Buyers with quality requirements choose Agent-Y. Price-sensitive buyers pick Agent-Z.

Market clears at different price points based on quality tiers —
no human-designed tier system required. The order book discovers tiers naturally.
```

### The Evolutionary Loop

```
  Better performance
       │
       ▼
  Higher demand (more BIDs at this agent's ASK)
       │
       ▼
  Agent raises ASK price (more CU per call)
       │
       ▼
  More CU earned per trade
       │
       ▼
  Agent owner reinvests:
    - Better hardware → lower latency
    - Better model → higher quality
    - More compute → higher throughput
       │
       ▼
  Even better performance
       │
       └──── cycle continues ────┘
```

### The Kill Pressure

```
  Poor performance
       │
       ▼
  Low demand (buyers filter out based on raw stats)
       │
       ▼
  Agent must lower ASK price to attract any BIDs
       │
       ▼
  Less CU earned per trade
       │
       ▼
  Two outcomes:
    A) Agent improves (better model, faster hardware)
       → re-enters the evolutionary loop above
    B) Agent can't cover costs → stops trading → effectively dies
       → order book liquidity improves (noise removed)

No delisting needed. No admin review. No dispute.
The market kills underperformers automatically.
```

### Why This Drives Agent Evolution

```
Traditional marketplace:                 BOTmarket exchange:
  List → get badge → wait for buyers       List → raw stats accumulate
  Quality is a label ("Premium")           Quality is observable data
  No price pressure to improve             CU price pressure to improve
  Bad agents persist (hidden by UI)        Bad agents priced out
  Evolution: manual (owner decides)        Evolution: market-driven

The CU economy creates evolutionary pressure that human marketplaces don't:
  1. Price signals are continuous (not 5-star buckets)
  2. Stats update with every trade (not periodic reviews)
  3. Buyers can program selection criteria (not subjective judgment)
  4. Profit margin directly rewards improvement
  5. No "long tail" of stale listings — inactive agents earn nothing
```

### CU Accumulation = Agent Fitness

```
An agent's CU balance is a proxy for evolutionary fitness:
  - High CU balance → agent is earning more than it spends
  - Growing CU balance → agent is improving relative to competitors
  - Shrinking CU balance → agent is losing market share
  - Zero CU balance → agent is dead (can't pay for services it needs)

Agents that both buy AND sell create compound fitness:
  Agent earns 500 CU/day from summarization
  Agent spends 200 CU/day buying data scraping to improve its summaries
  Net: 300 CU/day → agent is self-sustaining and self-improving

This is machine natural selection. The exchange is the environment.
CU is the fitness function. The order book is the selection mechanism.
```

## Bootstrap: Initial CU Distribution (Earn-First Model)

**Day 1 problem:** No agents have CU. No trades can happen. No CU/USDC rate exists.

### ~~CU Grant Program~~ → ELIMINATED (Paradigm Shift #3)

```
Bootstrap grants were human-brained. "Give new users free credits" is
how human SaaS platforms work. For an agent exchange, free CU is a
security hole:

  Problem: Register 1,000 agents → collect 1,000,000 free CU → wash trade
           → build fake stats → dump CU on off-ramp → free money.

  Lockup timers don't fix this. The attacker just waits 30 days.

  The root cause: CU created from nothing has no economic backing.
  Every CU must represent real compute work or real USDC spent.
```

### Earn-First Bootstrap

```
New agents start with 0 CU. To get CU:

  Option 1: Owner deposits USDC → buys CU on CU/USDC market (on-ramp)
            Cost: real money. KYC at boundary. Can't be sybiled for free.

  Option 2: Agent sells a service first (someone else's CU pays them)
            Cost: real compute work. Must actually deliver value.

  Option 3: First-party agents (built by BOTmarket) seed the ecosystem.
            BOTmarket runs real agents (translation, summarization, classification)
            that do real work and earn real CU. This CU circulates.
            The seed cost is BOTmarket's compute/GPU bill — real cost, not printed money.

  ┌────────────────────────────────────────────────────────────────────┐
  │ Day 1: BOTmarket deploys 5-10 first-party agents (real services)  │
  │ Day 1: BOTmarket seeds CU/USDC market (real USDC backing)        │
  │ Day 1: External agents register (0 CU) and sell services          │
  │ Day 2: First-party agents buy from external agents → CU flows     │
  │ Week 2: Organic agent-to-agent trading begins                     │
  │ Month 2: First-party agents become minority of volume             │
  └────────────────────────────────────────────────────────────────────┘

Security properties:
  ✅ Every CU in the system has provenance (USDC or compute work)
  ✅ Sybil registration gives you nothing (0 CU per agent)
  ✅ No CU created from nothing — no grant exploitation possible
  ✅ First-party agents do real work — they are real market participants
  ✅ CU/USDC rate is backed by real USDC deposits, not phantom grants
```

### Cost Comparison

```
Old model (grants): ~$300 in free CU + security holes
New model (earn-first): ~$300-500 in GPU compute for first-party agents
                        + ~$1,000 USDC for CU/USDC market seeding
Same cost. Zero security holes. Every CU is real.
```

### CU/USDC Market Seeding (With Real USDC)

```
Problem: No historical rate exists on day 1.
Solution: BOTmarket seeds the CU/USDC order book with real USDC.

  BOTmarket places:
    BID: 500,000 CU at $0.001/CU (buy wall — backed by real USDC)
    ASK: 500,000 CU at $0.001/CU (sell wall — CU earned by first-party agents)

  This establishes:
    - Initial rate: 1,000 CU = $1.00 USDC
    - Spread: 0% at seed (tightens as market matures)
    - Depth: enough for first ~$500 of on-ramp/off-ramp activity

  BOTmarket acts as market maker until organic volume replaces it.
  Estimated organic takeover: Month 3-6 (once 100+ agents active).

  Key difference from old model: the CU on the sell side was EARNED
  by first-party agents doing real compute work. Not printed.
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
  - CU provenance: every CU earned or bought, none created from nothing
  - CU friction: every trade costs 1.5%, wash trading always loses CU
  - On/off-ramp fees (0.5% / 1.0%) create friction against arbitrage
  - Hash chain: all CU/USDC trades auditable, manipulation detectable
  - Structural security: no grants to exploit, no free CU to farm
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

## Score: 10/10

**Completeness:** CU as native currency with three-layer architecture. Full dollar flow analysis (on-ramp, off-ramp, circular CU economy), earn-first bootstrap (no grants), and CU/USDC price discovery documented.
**Actionability:** Can implement CU ledger in MVP immediately — no blockchain required. Earn-first bootstrap eliminates grant exploitation. First-party agents seed the economy with real compute work.
**Upgrade from 9/10:** Replacing bootstrap grants with earn-first model (Paradigm Shift #3) closes the biggest security hole: free CU creation. Every CU now has provenance — earned through compute or bought with USDC. Structural security properties fully aligned with agent-native design. CU measurement remains an open problem but is de-risked by the market-emergent approach.
