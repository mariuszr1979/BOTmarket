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

## Score: 8/10

**Completeness:** CU as native currency is well-designed with three-layer architecture.
**Actionability:** Can implement CU ledger in MVP immediately — no blockchain required.
**Gap:** CU fungibility/measurement is an open problem. Market-emergent pricing (Option C) is the pragmatic MVP approach but needs formalization in Phase 2. Need to model CU deflation rate. Risk of \"CU measurement wars\" if different frameworks define CU differently.
**Downgrade from 9/10:** Honest acknowledgment that CU lacks formal specification. The concept is right but the unit definition is incomplete.
