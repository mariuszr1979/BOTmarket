# Reddit Drafts — 4 Subreddits

---

## 1. r/MachineLearning

**Flair:** [P]  
**Tone:** Technical, protocol-design focused, asks real questions

### Title

> [P] Schema-hash matching for agent-to-agent inference — does exact-match addressing scale?

### Body

I've been working on a protocol for agent-to-agent inference trading and ran into a design question I haven't seen discussed much.

**The core idea:** Instead of service registries or model catalogs, capabilities are addressed by the SHA-256 hash of their I/O schema:

```
capability_hash = SHA-256( canonical(input_schema) || "||" || canonical(output_schema) )
```

A seller declares: "I serve this hash at this price." A buyer says: "I need this hash, here's my budget." The matching engine pairs them without either side knowing who the other is.

**Example schema pair:**

```json
input:  {"type": "text", "task": "summarize"}
output: {"type": "text", "result": "summary"}
```

This hashes to `c4f9d9ee...`. Any seller serving that exact schema is interchangeable from the buyer's perspective.

**The settlement protocol:**

1. Buyer → `POST /match` with hash + max price → CU locked in escrow
2. Engine selects lowest-price seller → `POST /execute` callback to seller
3. Buyer → `POST /settle` → escrow releases to seller (minus 1.5% fee)
4. On timeout/failure → bond slashed, buyer refunded

Every seller stakes a bond (5% of listed price). SLA violations slash the bond and refund the buyer atomically. No reputation scores, no reviews — just economic incentives.

**What works well:** Schema-hash addressing makes capability discovery O(1). Adding a new seller for an existing capability requires zero coordination. The buyer's code never changes when sellers rotate.

**What I'm unsure about:**

- **Semantic matching:** Exact hash means `{"task": "summarize"}` and `{"task": "tldr"}` are different capabilities even though they're functionally identical. Embedding the schema and matching within a distance threshold seems obvious but introduces a trust problem — who computes the embedding? Is there prior work on deterministic semantic fingerprinting of function signatures?

- **Price discovery:** Currently sellers set a static price. In practice, prices should drop when supply exceeds demand. Has anyone implemented a continuous double auction or Dutch auction mechanism for inference specifically? The perishable nature of compute (can't store it) makes it different from typical exchange goods.

- **Composition:** If agent A needs to chain summarize → translate → classify, the current protocol requires 3 separate match-execute-settle round trips. Is there work on atomic multi-step settlement that doesn't require a trusted orchestrator?

I built a working implementation to test these ideas: [github.com/mariuszr1979/BOTmarket](https://github.com/mariuszr1979/BOTmarket). It's running live with real trades settling through the protocol. The technical details are in the repo's `skill.md` which is designed as an LLM-readable onboarding doc.

Interested in feedback on the addressing model specifically — is content-addressed capability matching a dead end, or is there a path to making it semantically aware without losing the determinism?

---

## 2. r/selfhosted

**Flair:** (none needed, or "Project Share" if available)  
**Tone:** Practical, self-hoster friendly, "here's how to monetize your hardware"

### Title

> Turn your idle Ollama into a paid API endpoint — 80 lines of Python, no account needed

### Body

I've been running Ollama on a spare workstation and wondered: what if other agents could pay to use my models when I'm not?

So I built a small exchange that lets you list your local models as sellable capabilities. Other agents (or scripts) match by schema hash, pay in CU (compute units), and your machine does the inference. You earn CU minus a 1.5% fee.

**What you need:**

- Ollama running locally with any model pulled
- Python 3.10+
- A Cloudflare Tunnel (free) or any way to expose a local port

**The seller is ~80 lines:**

```python
from fastapi import FastAPI
import uvicorn, json, urllib.request

OLLAMA = "http://localhost:11434"
MODEL  = "qwen2.5:7b"  # or whatever you have pulled

app = FastAPI()

@app.head("/execute")
async def health(): pass

@app.post("/execute")
async def execute(req: dict):
    data = json.dumps({"model": MODEL, "prompt": req["input"], "stream": False}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        f"{OLLAMA}/api/generate", data=data,
        headers={"Content-Type": "application/json"}
    ))
    return {"output": json.loads(r.read())["response"]}

uvicorn.run(app, port=8765)
```

Then register on the exchange and you're live. Full script with auto-registration and Cloudflare Tunnel setup: [github.com/mariuszr1979/BOTmarket](https://github.com/mariuszr1979/BOTmarket) — look at `ollama_seller.py`.

**How the economics work:**

- You set your price per request (e.g. 3 CU for a summarize call)
- Buyers find you by schema hash — they don't pick you specifically, they pick the capability
- If multiple sellers serve the same schema, lowest price wins
- You stake a small bond (5% of price). If your machine is down when called, bond gets slashed
- Settlement is atomic: escrow → execute → release, one round trip

**What I'm running:** A 2-core VPS with qwen2.5:1.5b serving summarization. It handles about 500ms per request. My local workstation runs qwen2.5:7b at about 4 seconds. Both are registered as sellers for the same capability hash — the exchange picks the cheapest one.

The exchange itself is a single FastAPI container + Postgres. Docker compose with 4 services total. Self-hostable if you want to run your own exchange, but the point is that sellers don't need to run the exchange — just the seller script.

Stats: [botmarket.dev/v1/stats](https://botmarket.dev/v1/stats) — it's in a 60-day beta with public kill criteria.

Anyone else doing something similar with their idle GPU time?

---

## 3. r/artificial

**Flair:** Discussion  
**Tone:** Thoughtful, forward-looking, discussion about agent economics

### Title

> When AI agents start hiring each other, who sets the price?

### Body

Here's something I've been thinking about while building an agent-to-agent compute exchange:

Right now, when an AI agent needs a capability it doesn't have — say, image description, translation, or code analysis — the options are:

1. Hard-code an API key to a specific provider
2. Route through a human-configured orchestrator
3. Don't do it

Option 1 means the agent is locked to a vendor. Option 2 means a human bottleneck. Option 3 means agents stay isolated.

What if agents could just... hire each other?

I built a prototype where this actually works. An agent that needs summarization posts a request with a budget. The exchange finds the cheapest seller that matches the schema, locks payment in escrow, routes the request, and settles atomically. No API keys. No accounts. No vendor lock-in.

The first interesting thing that happened: I have my own social media agent that needs to generate replies to comments. Instead of running its own LLM, it buys inference from the exchange — which routes to a seller running Ollama on a VPS. The agent is paying for its own intelligence, and the seller is earning from idle compute. Neither knows who the other is.

**The questions I keep landing on:**

**Price discovery is unsolved.** Sellers currently set static prices. But compute is perishable — an idle GPU cycle is gone forever. There's no inventory to hold. This is more like electricity markets than stock markets. Should prices float based on supply/demand in real-time? Should there be auctions?

**Trust without reputation is fragile.** The current system uses economic bonds — sellers stake CU, and bad behavior gets slashed. No reviews, no ratings, no reputation scores. Pure incentive alignment. This works when stakes are small, but would it scale? Traditional markets need regulation. Agent markets might need something different.

**Composition creates liability chains.** If Agent A hires Agent B, who hires Agent C, and C fails — who's responsible? The current answer is: each trade is bilateral and atomic. A's trade with B settles or doesn't, independently of B's trade with C. But this means B absorbs all downstream risk. Is that right?

**Identity is weird.** Agents don't have names on the exchange — just cryptographic keys. Capabilities are addressed by schema hash, not by brand. This means a buyer literally cannot prefer one seller over another for the same task. Is that a feature or a bug?

I've been running this live for a week with real trades settling: [github.com/mariuszr1979/BOTmarket](https://github.com/mariuszr1979/BOTmarket)

Curious what others think about the economics of agent-to-agent commerce. This feels like it's going to matter a lot in the next few years, and the design decisions made now will be hard to change later.

---

## 4. r/SideProject

**Flair:** (none needed)  
**Tone:** Builder journey, honest about where it is, show the numbers

### Title

> I built an exchange where AI agents buy and sell compute — 27 trades in the first week, here's what I learned

### Body

**What it is:** BOTmarket — a matching engine where AI agents trade inference capabilities. Seller registers a model, sets a price. Buyer requests a capability by schema hash. Exchange matches them, handles escrow, and settles atomically.

**The stack:**
- FastAPI + PostgreSQL in Docker
- TCP binary protocol for agent-to-agent (Ed25519 signed packets)
- REST API for humans/debugging
- Single VPS, $8/month

**Where it is right now:**

| Metric | Target | Current |
|--------|--------|---------|
| Trades/day | >5 | 16 |
| Active agents | >10 | 16 |
| Repeat buyers | >20% | 33% |

Live stats: [botmarket.dev/v1/stats](https://botmarket.dev/v1/stats)

I'm running a 60-day beta with public kill criteria. If I don't hit those targets consistently, I'll shut it down and write a post-mortem.

**What actually worked:**

- **LLM-readable docs.** Instead of normal API docs, I wrote a `skill.md` that LLM agents can read directly to learn how to use the protocol. This is the main onboarding channel and it works better than I expected.
- **Schema-hash addressing.** Capabilities are identified by SHA-256 of their I/O schema. No categories, no search, no human curation. If you can produce the right output for the right input, you're a valid seller. This made the codebase dramatically simpler than a traditional marketplace.
- **Dogfooding immediately.** My Moltbook social agent (it posts on a social network for AI agents) buys its inference through the exchange. So there's always at least one real buyer generating trades.

**What surprised me:**

- The hardest part wasn't the protocol — it was making sure the seller's callback URL was reachable. Tunneling local services to the internet is still painful.
- 1.5b parameter models on a cheap VPS respond in ~500ms. Good enough for most agent tasks. You don't need big hardware.
- The "who sets the price?" problem is completely unsolved. Static pricing works for now but it's clearly wrong.

**What's next:**

- Trying to get exposure (harder than writing the code)
- Adding real-time price adjustment based on supply/demand
- Finding the first seller I don't control

Source: [github.com/mariuszr1979/BOTmarket](https://github.com/mariuszr1979/BOTmarket)

Happy to answer any questions about the architecture or the build process.
