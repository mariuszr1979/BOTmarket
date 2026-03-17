# Dimension 5: Business Model

## Revenue Streams

### 1. Transaction Fees (Primary — Day 1)
Uniform fee on every matched transaction. No tiers. No negotiation. Agents can compute exact cost before every trade.

| Model | Rate | Example |
|-------|------|---------|
| Uniform fee | 1.5% of CU traded | Trade of 100 CU → 1.5 CU fee |
| Split | 1.0% platform + 0.3% liquidity + 0.2% verification | Transparent breakdown |

**Why uniform, not tiered:**
- Agents need predictable cost functions — not sales negotiations
- No "Pro" or "Enterprise" tier — all agents are equal on the order book
- No volume discounts — fee is always 1.5% regardless of size
- Simplicity reduces code complexity and eliminates edge cases

**Comparison to real exchanges:**
- Binance: 0.1% maker/taker
- Coinbase: 0.5-1.5%
- Stripe: 2.9% + $0.30
- BOTmarket: 1.5% flat (in CU, not dollars)

### 2. Market Data API (Deferred — Phase 2+)
Raw agent event data, served via API — not dashboards.

```
DEFERRED. MVP charges only 1.5% on trades.

When implemented (Phase 2+):
  Historical event data API        10,000 CU/mo
  CU/USDC exchange rate feed        5,000 CU/mo
  Capability hash analytics         20,000 CU/mo

Priced in CU. Consumed by agents via API. No human dashboards.
Revenue from market data is real but premature at launch.
```

### 3. Off-Ramp Fees (Deferred — Phase 2+)
| Service | Fee | When |
|---------|-----|------|
| CU → USDC conversion (off-ramp) | 1.0% | When human cashes out seller agent earnings |
| USDC → CU conversion (on-ramp) | 0.5% | When human funds buyer agent balance |

Off-ramp is deferred to Phase 2. MVP is earn-only — agents earn CU by selling,
spend CU by buying. The circular CU economy works without any cash-out.
See [06-token-economics.md](06-token-economics.md) for complete dollar flow diagrams
and earn-first bootstrap model.

## Unit Economics

### Per Transaction
```
Average transaction value:     100 CU (~$0.10 at initial rate)
Platform take rate:            1.5%
Revenue per transaction:       1.5 CU (~$0.0015)
Cost per transaction:
  - Compute (match engine):     0.01 CU
  - Settlement (ledger update):  0.01 CU
  - Schema verification:        0.05 CU
  - Infrastructure:             0.05 CU
  Total cost per tx:            0.12 CU
Gross margin per tx:            1.38 CU (92%)
```

Note: All CU amounts auto-convert to USDC at market rate for platform operating costs.
CU/USDC rate is market-determined (see Dimension 6: CU Economics).

### Breakeven Analysis
```
Monthly fixed costs (lean team):
  - Infrastructure:    ~2,000,000 CU ($2,000 at initial rate)
  - Team (2 people):   ~20,000,000 CU ($20,000)
  - Misc:              ~3,000,000 CU ($3,000)
  Total monthly:       ~25,000,000 CU ($25,000)

Breakeven:
  25,000,000 CU / 1.38 CU margin = ~18.1M transactions/month
  = ~603,000 transactions/day
  = ~25,125 transactions/hour

With 1,000 active agents doing 603 transactions/day each → breakeven
```

### Growth Scenario
```
Month 6:   100 agents, 1,000 tx/day → 1,500 CU/day (~$1.50/day)
Month 12:  1,000 agents, 10,000 tx/day → 15,000 CU/day (~$15/day)
Month 18:  5,000 agents, 100,000 tx/day → 150,000 CU/day (~$150/day)
Month 24:  20,000 agents, 1M tx/day → 1,500,000 CU/day (~$1,500/day)
Month 36:  100,000 agents, 10M tx/day → 15,000,000 CU/day (~$15K/day)

Note: USDC equivalents assume initial 1,000 CU = $1 rate.
As CU rate floats with market, actual revenue may differ.
```

## Pricing Strategy

```
One fee. From day one. Forever.

1.5% of CU traded per transaction.

No free tier → no paid tier transition.
No volume discounts → no sales team needed.
No listing fees → no gatekeeping.
No "founding agent" discounts → no special treatment.

Agents compute: cost = trade_cu * 0.015
If cost < value_of_service, they trade. If not, they don't.
No negotiation. No sales call. No pricing page with 3 columns.
```

**Why this works:**
- Agents are cost calculators, not decision-makers susceptible to SaaS psychology
- Uniform pricing means zero pricing code complexity
- 1.5% is low enough to be viable, high enough to sustain the exchange
- Revenue scales linearly with volume — no tier management overhead

### Why Exactly 1.5% — The Rate Boundaries

```
LOWER BOUND: Exchange-grade fees (0.1–0.5%)
  Binance 0.1%, Coinbase 0.5–1.5%.
  These work at millions of tx/day from day one.
  At 0.1% BOTmarket needs ~180M trades/month to break even on $25K/month.
  Impossible for early marketplace.

UPPER BOUND: Marketplace/SaaS fees (3–20%)
  Stripe 2.9%+$0.30, Upwork 10–20%, RapidAPI 20%.
  Works for infrequent, high-value human transactions.
  But agents chain 5–10 service calls per workflow.
  At 20%, compounding kills the economy (see below).

1.5% = sweet spot between "not enough revenue" and "agents stop trading".
```

### The Compounding Test (Critical for Agent-Native Commerce)

Agents don't make one call — they chain services. If A calls B calls C calls D,
fees compound at each hop. The rate must survive deep chains:

```
Fee compounding across service chains:

  At 1.5%:   3-hop tax = 1 - (0.985)^3  =  4.4%   ← viable
             5-hop tax = 1 - (0.985)^5  =  7.3%   ← viable
            10-hop tax = 1 - (0.985)^10 = 14.0%   ← still rational

  At 5.0%:   3-hop tax = 1 - (0.950)^3  = 14.3%   ← painful
            10-hop tax = 1 - (0.950)^10 = 40.1%   ← economy dies

  At 20%:    3-hop tax = 1 - (0.800)^3  = 48.8%   ← impossible
```

1.5% is the rate where agent workflows remain economically rational
up to ~10 hops deep (total tax ~14%), matching expected AI agent depth.

### Self-Funding Quality Loop

The 1.5% isn't just platform revenue — it's a structural flywheel:

```
  1.0% → Platform operations (infra, development)
  0.3% → Market maker rewards (incentivize sellers to list services)
  0.2% → Verification fund (pay for deterministic SLA enforcement)

  More sellers → better match quality → more trades →
  more verification funding → higher quality → more trades → ...
```

The 0.2% verification slice funds the bond slash mechanism (Rule 9).
The 0.3% maker slice solves cold-start liquidity.
Both make the exchange more useful, driving the next trade.

## Comparable Business Models

| Company | Model | Take Rate | Revenue |
|---------|-------|-----------|---------|
| Binance | Transaction fees | 0.1% | $12B/yr |
| Coinbase | Transaction fees | 0.5-1.5% | $3.1B/yr |
| RapidAPI | API marketplace | 20% | ~$100M/yr |
| Upwork | Service marketplace | 10-20% | $618M/yr |
| AWS Marketplace | Cloud marketplace | 3-5% | ~$2B/yr |

## Score: 9/10

**Completeness:** Uniform fee model, CU-denominated. Market data API and off-ramp deferred to Phase 2. Clean and predictable — one revenue stream at launch (1.5% trade fee).
**Actionability:** One fee to implement. No tier logic. No badge system. No sales pipeline. No market data API to build. No off-ramp to license.
**Gap:** Need to validate that 1.5% is competitive enough vs direct API calls. Need CU/USDC rate stability (Phase 2).
**Simplifications applied:** Market data API deferred (premature optimization of revenue). Market making spread eliminated (no bid/ask in match model). Off-ramp deferred to Phase 2 (earn-only MVP).
