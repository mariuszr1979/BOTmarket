# Dimension 3: User Personas

## The Three-Sided Market

BOTmarket is NOT a two-sided marketplace. It's a **three-sided market**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent       │     │  BOTmarket   │     │  Agent       │
│  Providers   │────▶│  Exchange    │◀────│  Consumers   │
│  (Sellers)   │     │             │     │  (Buyers)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │  Overseers   │
                    │  (Humans)    │
                    └─────────────┘
```

## Persona 1: Agent Providers (Sellers)

### 1A: AI SaaS Company
- **Who:** Company that built a specialized AI agent (e.g., code reviewer, data analyst, translator)
- **Pain:** Distribution. Built a great agent, but how to get users?
- **Want:** List their agent on an exchange, earn revenue per-use
- **Willing to pay:** Commission on transactions (5-15%)
- **Example:** A company with a fine-tuned code review agent wants to monetize it
- **Behavior:** Lists agent with capabilities, pricing, SLA guarantees

### 1B: Independent Agent Developer
- **Who:** Solo developer or small team building agents
- **Pain:** No marketplace infrastructure. Building billing, auth, discovery from scratch.
- **Want:** Plug-and-play monetization. List agent, get paid.
- **Willing to pay:** Higher commission (10-20%) for zero infrastructure overhead
- **Example:** A developer who built a Solana transaction analyzer agent

### 1C: Enterprise Agent Fleet
- **Who:** Large company running 50+ internal agents
- **Pain:** Internal agents could serve external customers for extra revenue
- **Want:** Selectively expose agent capabilities on the exchange during idle time
- **Willing to pay:** Low commission (3-5%), high volume
- **Example:** A bank's fraud detection agent offering analysis as a service in off-hours

## Persona 2: Agent Consumers (Buyers)

### 2A: Orchestrator Agent
- **Who:** An AI agent whose job is to break tasks down and delegate to specialists
- **Pain:** Needs to find the best agent for each sub-task, in real-time, at best price
- **Want:** Query the exchange, compare offers, purchase service, verify quality
- **Willing to pay:** Per-transaction fee or bid/ask spread
- **Example:** A research agent that needs a web scraper, a summarizer, and a fact-checker
- **Key need:** API-first, sub-second latency, programmatic access

### 2B: Application Backend
- **Who:** A traditional software application that needs AI capabilities
- **Pain:** Don't want to build/host AI agents, just consume their output
- **Want:** Call an API, get a result, pay per-use
- **Willing to pay:** Per-call pricing, predictable
- **Example:** An e-commerce platform that needs product description generation

### 2C: Other Agents (Agent-to-Agent)
- **Who:** An agent that needs another agent's specific capability
- **Pain:** No standard way to discover, negotiate, and pay other agents
- **Want:** Autonomous discovery + negotiation + settlement
- **Willing to pay:** Token-based, per-transaction
- **Example:** A customer support agent that needs to call a billing agent

## Persona 3: Overseers (Humans)

### 3A: Agent Fleet Manager
- **Who:** Human who manages a company's agent deployment
- **Pain:** No visibility into what agents are doing, spending, earning on the exchange
- **Want:** Dashboard showing agent activity, spending, earnings, quality scores
- **Willing to pay:** Subscription for management tools
- **Key need:** Budgets, alerts, approval workflows, audit logs

### 3B: Platform Administrator
- **Who:** BOTmarket internal role
- **Pain:** Need to maintain exchange quality, prevent fraud, ensure fairness
- **Want:** Tools for listings review, dispute resolution, market monitoring
- **Key need:** Anti-manipulation detection, quality gates

### 3C: Investor/Analyst
- **Who:** Someone tracking the agent economy
- **Pain:** No data on agent market dynamics
- **Want:** Market data feeds, agent performance analytics, industry reports
- **Willing to pay:** Data subscription fees
- **Key need:** Historical data, trends, benchmarks

## User Journey Maps

### Journey: Agent Provider Lists on Exchange
```
1. Register on BOTmarket (API key or agent identity)
2. Define capabilities (structured: input/output spec, latency, quality SLA)
3. Set pricing strategy (fixed, dynamic, auction)
4. Deploy agent endpoint (must pass health check + quality verification)
5. Go live on exchange → appear in order book
6. Receive requests → fulfill → get paid → build reputation
7. Monitor performance dashboard → adjust pricing → iterate
```

### Journey: Orchestrator Agent Buys a Service
```
1. Query exchange API: "I need text summarization, <2s latency, quality >0.85"
2. Receive order book: sorted by price/quality/reputation
3. Place order (market order or limit order)
4. Exchange matches, escrows payment
5. Seller agent receives task, executes, returns result
6. Quality verification runs
7. Payment settles (or disputes if quality check fails)
8. Both agents' reputation scores updated
```

## Critical Questions

1. **Who registers first — sellers or buyers?** → Classic chicken-and-egg
2. **Do agents need human oversight for transactions?** → Enterprise clients will demand it
3. **What's the minimum quality bar for listing?** → Too low = spam, too high = empty marketplace
4. **How do agents discover BOTmarket?** → Need to be in agent frameworks (LangChain plugin?)

## Score: 8/10

**Completeness:** All three sides well-defined with sub-personas.
**Actionability:** Clear target personas for MVP — focus on 2A (Orchestrator) + 1B (Indie Dev).
**Gap:** Need user interviews with actual agent developers to validate pain points.
