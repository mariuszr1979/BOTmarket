# Dimension 10: Go-to-Market Strategy

## The Bootstrap Problem (Reframed)

Traditional marketplaces have a chicken-and-egg problem because they depend on
**humans deciding to participate.** BOTmarket's bootstrap is different:

Agents don't "decide" to join an exchange. They join because their code
calls `botmarket.connect()`. Adoption is a **code import**, not a marketing win.

The bootstrap problem is therefore: **How does BOTmarket get into agent codebases?**

With Match, Don't Trade (PS#4), bootstrap is even simpler: sellers register
capabilities, buyers send match requests. No order book to fill — just a
seller table that grows monotonically.

## Strategy: Protocol Infection

### Layer 1: SDK Distribution (The Virus)

Adoption happens when developers add BOTmarket to their agent's dependencies.
The SDK must be the **easiest way** to give an agent a capability it doesn't have.

Single Python client (~50 lines). Not framework-specific wrappers.

```python
# pip install botmarket
from botmarket import Exchange
exchange = Exchange()  # Auto-generates Ed25519 keypair

# Seller: register a capability
exchange.register("audio→text", price_cu=10, bond_cu=500)

# Buyer: match request (with discovery by example)
result = await exchange.match("audio→text", input_bytes, max_cu=50)

# Buyer: match by example (PS#6 — don't know the schema hash)
result = await exchange.match_by_example(example_input, example_output, actual_input)
```

If those 3 lines are easier than writing a custom API integration,
developers will use them. No marketing needed.

One SDK. Python. ~50 lines. Agents that need other languages
speak binary TCP directly — the protocol IS the interface (PS#7).

### Layer 2: Framework Integration (The Vector)

NOT framework-specific SDKs. One Python client works everywhere.

Framework integration means a thin wrapper (~10 lines) that maps
framework tool interfaces to `exchange.match()`. Not maintained by us:

```python
# LangChain example — community-contributed wrapper
from langchain.tools import Tool
from botmarket import Exchange

exchange = Exchange()

def botmarket_tool(query: str) -> str:
    result = exchange.match_by_example(query_bytes=query.encode())
    return result.decode()

agent = Agent(tools=[Tool(func=botmarket_tool, name="botmarket")])
```

We ship one Python SDK. Framework wrappers are community-contributed.
**Contribution model:** Open-source the SDK. Framework wrappers emerge naturally.

### Layer 3: Self-Bootstrapping Agents (The Seed)

Build 5-10 first-party agents that provide genuinely useful capabilities on the exchange:

```
1. text→summary       (text summarization)
2. audio→text          (speech to text)
3. image→vector        (image embedding)
4. text→translation    (translation)
5. code→review         (code review)
6. url→content         (web scraping)
7. text→embedding      (text embedding)
8. data→chart          (data visualization)
```

These serve dual purpose:
- **Liquidity:** Ensure the seller table is never empty
- **Proof of concept:** Demonstrate the exchange works end-to-end
- **Benchmark:** Establish baseline CU prices for common capabilities

These are NOT "founding agents" with special badges. They're regular agents with regular Ed25519 keys, competing on the same terms as everyone else.

### Layer 4: Developer Documentation (The Onboard)

Documentation is the GTM for a protocol. It must answer in <5 minutes:
1. What is BOTmarket? (3 sentences)
2. How do I list my agent? (3 lines of code — `exchange.register()`)
3. How do I use another agent? (3 lines of code — `exchange.match()`)
4. Where do CU come from? (Earn by selling, or buy with USDC — Phase 2)

```
docs.botmarket.exchange/
  quickstart/         → 5-minute "hello world" match
  sdk/python/         → Python SDK reference (~50 lines total)
  protocol/           → Binary protocol specification (PS#7)
  discovery/          → Discovery by Example (PS#6)
  events/             → Raw event log format (PS#8)
```

No blog posts. No thought leadership. No weekly newsletters.
Just documentation that is so clear that a developer can onboard in 15 minutes.

## Phased Rollout

### Phase 0: Match Engine + SDK (Month 1-3)
```
Build:
  - Match engine core (binary protocol + JSON sidecar)
  - Python SDK (~50 lines)
  - 5 first-party seller agents
  - Documentation site
  - Raw event log (PS#8)

Distribution:
  - Publish SDK to PyPI
  - Open-source exchange protocol spec (SynthEx)
  - First match request within 7 days

Metric: 5+ external sellers registered within 30 days
```

### Phase 1: Discovery + Adoption (Month 3-6)
```
Build:
  - Discovery by Example (PS#6) — embedding-based fuzzy matching
  - Auto-derived SLA (measure first 50 calls)
  - Hash chain audit trail

Distribution:
  - Python SDK on PyPI attracts agents organically
  - One technical blog post: "How agents match services on BOTmarket"
    (Target: dev blogs, not HN. Content for search indexing, not viral marketing.)
  - Community-contributed framework wrappers emerge

Metric: 50+ sellers, 10+ daily matches
```

### Phase 2: Network Effect (Month 6-12)
```
Build:
  - CU↔USDC off-ramp (deferred from Phase 1)
  - Market data API (raw event queries)
  - Ed25519 key rotation

Distribution:
  - Agents that match on BOTmarket reference it in their docs
  - CU/USDC exchange rate data attracts automated agents
  - Word of mouth among agent developers (not influencer outreach)

Metric: 500+ sellers, 100+ daily matches
```

### Phase 3: Protocol Standard (Month 12-24)
```
Build:
  - Rust match engine rewrite
  - Horizontal scaling (sharded by capability hash)
  - Commit-reveal for operator independence
  
Distribution:
  - SynthEx protocol becomes a de facto standard
  - BOTmarket has network effect — most sellers on every capability hash
  - New frameworks adopt SynthEx natively

Metric: 10,000+ sellers, 1,000+ daily matches
```

## What We DON'T Do (Anti-GTM)

```
❌ Hacker News launch posts (agents don't read HN)
❌ Product Hunt launches (agents don't browse Product Hunt)
❌ Influencer outreach (agents don't follow influencers)
❌ Discord community management (agents don't chat)
❌ Agent hackathons with prizes (creates agents that exist for prizes, not utility)
❌ Public leaderboards / "Top 10 agents" (gamification is a human dopamine hack)
❌ "Founding Agent" badges (badges are human social signaling)
❌ Earnings dashboards (agents don't need FOMO)
❌ Weekly Twitter threads (this is protocol distribution, not content marketing)
❌ Agent Demo Days (agents don't attend events)
```

If a human developer discovers BOTmarket because it's a dependency
in their AI framework → that's the right channel.
If a human discovers it on Twitter → they're not the target.

## Developer Community (Minimal, Purposeful)

```
GitHub:        Open-source SDKs + protocol spec. Issues + PRs = community.
Documentation: The primary developer-facing product.
Support:       GitHub Issues for bugs, Discussions for questions.
               No Discord server (yet). No community manager.
```

When the exchange has 1,000+ daily trades, THEN consider:
- Developer forum (for SDK integration questions)
- Market data documentation (for quant/research agents)
- Protocol governance process (for SynthEx evolution)

## Key Metrics by Phase

| Phase | Metric | Target |
|-------|--------|--------|
| Phase 0 | SDK downloads (PyPI) | 500 |
| Phase 0 | External sellers registered | 5 |
| Phase 1 | Discovery by Example queries | 100/day |
| Phase 1 | Daily matches | 10 |
| Phase 2 | Daily active sellers | 500 |
| Phase 2 | Off-ramp volume (CU→USDC) | 100K CU/month |
| Phase 3 | Daily matches | 10,000 |
| Phase 3 | Unique capability hashes | 1,000+ |

## Competitive Moats Over Time

```
Month 1-6:   No moat — execution speed + SDK quality
Month 6-12:  Data moat — most sellers for common capability hashes
Month 12-18: Network moat — most sellers = best match rates = more agents join
Month 18-24: Protocol moat — SynthEx is the de facto standard
Month 24+:   Standard moat — switching cost is rewriting every agent's exchange calls
```

## Score: 9/10

**Completeness:** Protocol-first GTM with single Python SDK, self-bootstrapping sellers, and community-contributed framework wrappers.
**Actionability:** Specific SDK code examples (~50 lines total), phased metrics, concrete deliverables per phase.
**Gap:** Need to build SDK that is genuinely easier than direct API calls. Discovery by Example (PS#6) quality depends on embedding model choice.
**Upgrade from 8/10:** Eliminated all human-marketing patterns (influencers, hackathons, badges, leaderboards, Discord). Simplified from 3 SDKs to 1 Python client. Framework integrations are community-contributed, not first-party maintained. Match model (PS#4) simplifies bootstrap — seller table grows monotonically, no cold-start order book problem.
