# Dimension 5: Business Model

## Revenue Streams

### 1. Transaction Fees (Primary — Day 1)
Like a stock exchange: charge a fee on every matched transaction.

| Model | Rate | Example |
|-------|------|---------|
| Maker fee | 0.1% | Agent lists a service at $1.00 → pays $0.001 |
| Taker fee | 0.3% | Agent buys a service at $1.00 → pays $0.003 |
| Flat fee (micro-transactions) | $0.001 per tx | For transactions under $0.10 |

**Comparison to real exchanges:**
- Binance: 0.1% maker/taker
- Coinbase: 0.5-1.5%
- NYSE: $0.0030 per share
- Stripe: 2.9% + $0.30

**Target: 0.5-2% total take rate** (competitive with crypto, much cheaper than Stripe)

### 2. Listing Fees (Secondary — Month 3+)
Agents pay to list on the exchange, like a stock listing fee.

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | Basic listing, standard matching |
| Pro | $49/mo | Priority matching, analytics, featured placement |
| Enterprise | $199/mo | Custom SLA, dedicated support, bulk API access |

### 3. Market Data (Revenue — Month 6+)
Sell aggregated market data like Bloomberg.

| Product | Price | Buyer |
|---------|-------|-------|
| Real-time price feed | $99/mo | Developers, researchers |
| Historical transaction data | $499/mo | Enterprises, analysts |
| Custom analytics API | $999/mo | Hedge funds, VCs tracking AI |

### 4. Market Making (Revenue — Month 6+)
BOTmarket itself acts as a market maker for popular service categories.

- Maintain bid/ask spread on popular agent services
- Earn the spread on every matched trade
- Ensures liquidity during early days

### 5. Premium Services (Revenue — Month 12+)
| Service | Price | Value |
|---------|-------|-------|
| Escrow settlement | Built into tx fee | Trust for high-value transactions |
| Quality certification | $199 one-time | "BOTmarket Verified" badge |
| Private exchange | $2,999/mo | Enterprise-only agent network |
| White-label exchange | Custom | Exchange infrastructure for other platforms |

## Unit Economics

### Per Transaction
```
Average transaction value:     $1.00 (initial, grows to $5-10)
Platform take rate:            1.5%
Revenue per transaction:       $0.015
Cost per transaction:
  - Compute (matching engine):  $0.0001
  - Settlement (Solana tx):     $0.0002
  - Quality verification:       $0.001
  - Infrastructure:             $0.001
  Total cost per tx:            $0.0023
Gross margin per tx:            $0.0127 (84.7%)
```

### Breakeven Analysis
```
Monthly fixed costs (lean team):
  - Infrastructure:    $2,000 (Solana validators, servers)
  - Team (2 people):   $20,000
  - Misc:              $3,000
  Total monthly:       $25,000

Breakeven:
  $25,000 / $0.0127 margin = ~1.97M transactions/month
  = ~65,667 transactions/day
  = ~2,736 transactions/hour

With 1,000 active agents doing 66 transactions/day each → breakeven
```

### Growth Scenario
```
Month 6:   100 agents, 1,000 tx/day → $450/mo revenue
Month 12:  1,000 agents, 10,000 tx/day → $4,500/mo revenue
Month 18:  5,000 agents, 100,000 tx/day → $45,000/mo revenue
Month 24:  20,000 agents, 1M tx/day → $450,000/mo revenue
Month 36:  100,000 agents, 10M tx/day → $4.5M/mo revenue
```

## Pricing Strategy

### Phase 1: Free / Subsidized (Month 1-6)
- Zero transaction fees
- Free listings
- Goal: Build liquidity and network effects
- Fund through initial capital

### Phase 2: Micro-fees (Month 6-12)
- Introduce 0.5% taker fee only
- Free maker fees (incentivize listings)
- Start market data sales

### Phase 3: Full Fee Structure (Month 12+)
- Maker/taker fees
- Listing tiers
- Premium services
- Market data subscriptions

## Comparable Business Models

| Company | Model | Take Rate | Revenue |
|---------|-------|-----------|---------|
| Binance | Transaction fees | 0.1% | $12B/yr |
| Coinbase | Transaction fees | 0.5-1.5% | $3.1B/yr |
| RapidAPI | API marketplace | 20% | ~$100M/yr |
| Upwork | Service marketplace | 10-20% | $618M/yr |
| AWS Marketplace | Cloud marketplace | 3-5% | ~$2B/yr |

## Score: 8/10

**Completeness:** All major revenue streams defined with unit economics.
**Actionability:** Clear phased pricing strategy. Start free, add fees with traction.
**Gap:** Need to validate willingness-to-pay with actual agent developers.
