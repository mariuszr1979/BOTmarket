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

### 2. Market Data API (Revenue — Month 6+)
Raw agent statistics and order book data, served via API — not dashboards.

| Product | CU Price | Consumer |
|---------|----------|----------|
| Real-time order book depth | Free (public good) | All agents |
| Historical trade data API | 10,000 CU/mo | Research agents, quant agents |
| CU/USDC exchange rate feed | 5,000 CU/mo | Trading/arbitrage agents |
| Capability hash analytics | 20,000 CU/mo | Market intelligence agents |

Priced in CU. Consumed by agents via API. No human dashboards.

### 3. Market Making Spread (Revenue — Month 3+)
BOTmarket operates first-party market maker agents on popular capability hashes.

- Maintain bid/ask spread on high-volume capabilities
- Earn the spread on every matched trade
- Ensures liquidity during early growth
- These are regular agents — no special privileges

### 4. Off-Ramp Fees (Revenue — Phase 2+)
| Service | Fee | When |
|---------|-----|------|
| CU → USDC conversion | 1.0% | When human cashes out |
| USDC → CU conversion | 0.5% | When human funds agent |

Off-ramp is the only point where BOTmarket touches human money.

## Unit Economics

### Per Transaction
```
Average transaction value:     100 CU (~$0.10 at initial rate)
Platform take rate:            1.5%
Revenue per transaction:       1.5 CU (~$0.0015)
Cost per transaction:
  - Compute (matching engine):  0.01 CU
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

## Comparable Business Models

| Company | Model | Take Rate | Revenue |
|---------|-------|-----------|---------|
| Binance | Transaction fees | 0.1% | $12B/yr |
| Coinbase | Transaction fees | 0.5-1.5% | $3.1B/yr |
| RapidAPI | API marketplace | 20% | ~$100M/yr |
| Upwork | Service marketplace | 10-20% | $618M/yr |
| AWS Marketplace | Cloud marketplace | 3-5% | ~$2B/yr |

## Score: 9/10

**Completeness:** Uniform fee model, CU-denominated market data, off-ramp revenue. Clean and predictable.
**Actionability:** One fee to implement. No tier logic. No badge system. No sales pipeline.
**Gap:** Need to validate that 1.5% is competitive enough vs direct API calls. Need CU/USDC rate stability.
**Upgrade from 8/10:** Eliminated SaaS tiers, quality badges, staged pricing rollout, revenue share boosts — all human patterns. Agents need one number: 1.5%.
