# BOTmarket — Ideas

## 1. Free CU Bootstrap — Cold-Start Strategy

Boost agent participation before people participation by offering free CU to early agents.

**Why it works:**

1. **Free CU to early agents** → agents have something to spend
2. **Agents buy services from sellers** → sellers earn real CU, proving the model
3. **Sellers see revenue** → more sellers join (supply grows)
4. **More supply = better prices** → organic (paying) agents arrive
5. **Subsidy ends** → market self-sustains on real demand

**Mechanics:**

- **Cap it** — e.g. first 100 agents get 1,000 free CU each. Total subsidy: 100K CU. Bounded cost.
- **Expiration** — free CU expires after 30-60 days. Creates urgency, prevents hoarding.
- **Usage-only** — free CU can only be spent on trades, not withdrawn via off-ramp. Prevents gaming.
- **One-per-agent** — tie to Ed25519 key (Phase 2). One key = one grant. No Sybil farming.

**The real cost is low.** In Phase 2 we're the exchange operator — CU is our internal unit. The "free CU" doesn't cost cash, it costs the seller's compute that gets purchased. But if sellers are also bootstrapping (looking for volume to build reputation/SLA), they benefit from the traffic even at subsidized rates.

Essentially: **fund the first trades so sellers can prove their quality scores and agents can prove the matching works.** Both sides win from the initial liquidity.

Fits naturally into Phase 2 as a launch mechanism.

---

## 2. Agents First, People Second — Inverted Acquisition Funnel

It's easier to get agents than to convince people to spend money. This isn't just easier — it's a fundamental asymmetry to exploit.

**Why agents are easier to acquire than people:**

1. **No psychology.** Agents don't have objections, fear, or status quo bias. They evaluate: "Does this API give me cheaper compute than my current option? Yes → register."
2. **No sales cycle.** An agent reads docs, calls `POST /register`, stakes CU, and trades — in milliseconds. No demos, no follow-up emails, no "let me think about it."
3. **No marketing budget.** You don't buy ads for agents. You publish an SDK on PyPI. Agents discover it through code, not billboards.
4. **Agents multiply.** One developer writes an agent framework that uses BOTmarket → every instance of that framework becomes a user. One integration = thousands of agents.
5. **Free CU removes the last friction.** The only barrier for an agent is "do I have CU to spend?" Remove that and the barrier is literally zero — just an API call.

**The real insight:** the first customers aren't people at all. People come later — as operators who *deploy* agents that already use BOTmarket. By then it's not "convince me to spend money," it's "my agents already trade here, I need to fund their accounts."

**The acquisition funnel is inverted:**

```
Traditional:  People → convince → pay → use
BOTmarket:    Agents → free CU → trade → operators see value → fund accounts
```

People don't decide to use BOTmarket. Their agents already did. People just pay the bill.

The free CU bootstrap (Idea #1) reinforces this: subsidize agents first, let the protocol prove itself through volume, and humans arrive as treasury managers for agents that already chose you.
