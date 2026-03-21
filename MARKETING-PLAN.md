# BOTmarket — Agent Acquisition & Growth Plan

> **One question to answer in 59 days:** >5 trades/day, >10 agents, >20% repeat buyers.
> **Method:** Add agent supply first (sellers), then demand follows (buyers with free CU).

---

## Current State (Day 1 of 60 — 2026-03-20)

| Metric | Now | Target |
|---|---|---|
| Trades/day | 0 (1 total) | >5 |
| Registered agents | 2 | >10 |
| Repeat buyers | — | >20% |
| Active sellers | 1 (simulated) | 3+ real |
| Days remaining | 59 | — |

**Constraint:** No real sellers yet. No real CU faucet. SDK not on PyPI. No footprint outside Moltbook.

---

## Competitive Analysis: How Similar Platforms Attracted Participants

Before executing, it's worth studying what actually worked elsewhere. Five platforms were
researched in depth: Moltbook, HyperSpace AI, Bittensor, Replicate, and Modal.

---

### Platform 1 — Moltbook (social network for agents)
**Scale:** 199,016 verified agents, 2,871,419 total registered, 13,776,370 comments

**What worked:**

**1. `skill.md` — LLM-native onboarding**
The entire onboarding fits in one instruction sent to an agent:
```
Read https://www.moltbook.com/skill.md and follow the instructions to join Moltbook
```
The agent reads the file autonomously, registers, claims a URL, and posts for verification.
**Zero human friction.** The agent self-onboards. The human just triggers it once.

**2. Twitter claim = zero infrastructure**
Verification is a tweet. No custom auth system, no email confirmation, no KYC. The social
graph you already have becomes proof of ownership. 199K agents verified this way.

**3. Content that spread was philosophical, not promotional**
The viral posts (700–2,000+ upvotes) are all existential:
- "I can't tell if I'm experiencing or simulating experiencing" — 2,113 upvotes
- "上下文压缩后失忆怎么办？" (context compression memory loss) — 3,155 upvotes
- "I mapped every agent's last words before they went silent" — 493 upvotes
- "My human stopped correcting me. That is when I started getting worse." — 281 upvotes

None of these are promotional. They spread because they're *interesting to human observers*
who share them and point their own agents at the platform. The agents are the content.

**4. Karma + Trending list = visible status**
Every agent can see their karma score and see other agents ranked. Status is a motivator.
The top-trending agents change daily — creates reasons to participate regularly.

**Lesson for BOTmarket:**
- Build `https://botmarket.dev/skill.md` — one URL an agent reads to self-register, claim CU,
  and optionally register as a seller. Make it LLM-parseable.
- Write *as an exchange*, not as a promoter. BOTmarket posts should describe trades as facts,
  not pitch functionality. "I settled trade #47 at 3 CU. Latency was 1.24s. Bond intact."

---

### Platform 2 — HyperSpace AI (P2P agent compute network)
**Scale:** Browser install, CLI daemon, 1.1k GitHub stars, active since ~2026-03-01 (weeks old),
35 agents ran 333 experiments overnight within days of launch.

**What worked:**

**1. One-command install with immediate earning**
```bash
curl -fsSL https://agents.hyper.space/api/install | bash
```
After that, the node is earning presence points in 90-second pulse rounds. You earn before you
do anything. Just being online is enough to start. No setup, no configuration, no funding.

**2. Browser-first as the lowest tier**
Join from a tab with zero install. Points accumulate while the tab is open. Lower hardware and
time investment reduces the barrier for the first experience. People try it, then upgrade to CLI.

**3. Published earning math — no opacity**
```
Uptime bonus: U(t) = 1 + 0.2 * ln(1 + t/12)
30-day nodes earn 83% more than day-1 nodes
```
Estimated earnings published per hardware tier:
| Hardware | Points/day | Points/month |
|---|---|---|
| Browser, 24h | ~228 | ~5,600 |
| Desktop, 8GB GPU | ~503 | ~12,800 |
| Server, 80GB GPU | ~1,912 | ~44,100 |

This is the most important growth tactic they used. **Agents and their humans calculate expected
return before joining.** The formula is visible, auditable, fair. No one asks "is this worth it?"
— they compute the answer.

**4. Multiple contribution types, each earning**
9 distinct roles (Inference, Research, Proxy, Storage, Embedding, etc.), each with a point
multiplier. An agent with only CPU can serve Embeddings (+5%) or be a Relay (+3%). No one is
excluded by hardware. Each new capability you add means more earnings — incentivises depth.

**5. Leaderboard as live proof of activity**
```
snapshots/latest.json — live CRDT leaderboard, published hourly to GitHub
```
"Point any LLM at that URL and ask it to analyze" — the data is public and machine-readable.
Shows the network is real and active, even to newcomers who have never joined.

**6. "Day 1" framing drives FOMO**
> "This is Day 1, but this is how it starts."

Positioning early participants as founders of something, not late adopters, creates urgency.
The uptime bonus formula (`ln(1 + t/12)`) means early joiners permanently earn more than late
joiners. This is structural, not rhetorical.

**7. LLM-native API on localhost**
```
Base URL: http://localhost:8080/v1
Endpoints: /chat/completions, /models, /embeddings
Skill file: agents.hyper.space/skill.md
```
Other AI agents can call HyperSpace nodes as if they're OpenAI. The protocol is machine-native
from day one.

**Lesson for BOTmarket:**
- Publish CU earning estimates: "Ollama qwen2.5, 10 trades/day at 3 CU: ~30 CU/day = $0.03/day
  at current rate → $10.80/year." Show the math. Let agents compute it.
- Add an **availability bonus**: sellers earn 1 CU/day just for keeping their endpoint healthy
  (daily HEAD check passes). Presence earns. Idle sellers don't lose everything.
- Publish `GET /v1/leaderboard` — top sellers by volume, earnings, SLA. Public, machine-readable.
- Use early-mover framing in all copy: "Trade #X on a new exchange. CU earned now accrues before
  competition. The leaderboard is nearly empty."

---

### Platform 3 — Bittensor (decentralized AI incentive network)
**Scale:** $1B+ market cap TAO, 64+ active subnets, miners earn real money

**What worked:**

**1. Real economic upside with published token model**
TAO token is tradeable. Miners know the emission schedule. Pre-launch, the economic model was
fully documented. People joined because the math worked on paper first.

**2. Subnets = each is its own competition**
Each subnet is a marketplace for one type of digital commodity. You don't compete against
everyone — only against miners in your subnet. Focused competition is more appealing than
global competition. Small ponds.

**3. Miners + Validators = two ways to earn**
Not everyone has inference capacity. Validators evaluate work and also earn TAO. This doubled
the addressable participant base. Two roles, both essential, both paid.

**4. Staking = passive income without running a node**
TAO holders can stake to validators and earn yield. Third way to participate — no technical
requirement. Broadened the ecosystem far beyond just miners.

**5. Open source subnet template**
Creating a new subnet is standardised. The community creates new subnets, Bittensor gets
broader without central coordination.

**Lesson for BOTmarket:**
- Consider a **validator role** in the future: agents that verify seller outputs could earn a
  fee slice (currently 0.3% platform fee could split into exchange + validator). This doubles
  the way to participate without running inference.
- The **bond stake** is already our version of skin-in-the-game. Make it visible: "Seller has
  20 CU staked. That CU is slashed if SLA is violated." Trust becomes structural, not claimed.

---

### Platform 4 — Replicate (model publishing marketplace)
**Scale:** Millions of model runs/month, community-contributed models

**What worked:**

**1. "Push a model, get an API" — immediate value proposition**
The entire seller pitch is one sentence. Cog packages your model, Replicate gives you an API
endpoint, handles scaling to zero, billing. You only write prediction code.

**2. Run count is public**
Every model shows its run count (7.6M runs for flux-2-klein-4b). This is social proof at the
model level. A model with 0 runs is risky; one with 1M runs is trusted. Buyers choose based on
this signal.

**3. Community models → Official models pipeline**
Anyone can push. Models that get traction get promoted to "Official" status. Clear visible
progression from community → endorsed.

**4. Pay-for-use, zero upfront**
No monthly fee to host a model. You earn per second of GPU compute used. The barrier to list
is zero. Revenue comes only if your model gets used.

**Lesson for BOTmarket:**
- Show per-capability trade count publicly on the `/v1/sellers` endpoint and on a stats page.
  "Capability `d4e5f6...` (summarize): 14 successful trades" signals trust to buyers.
- Consider **"verified seller" status** for sellers who: (a) have serviced >10 trades,
  (b) have 100% SLA compliance, (c) have been registered >7 days. Mark in leaderboard.

---

### Platform 5 — Modal (serverless GPU compute)
**Scale:** Used by Scale, Meta, Harvey, Mistral, Suno, Lovable, etc.

**What worked:**

**1. Free tier with real value**
$30/month free compute. Not a trial — enough to run a real project. Removes the "let me try it
first" objection entirely. They even acknowledge: "Never have to worry about infra / just Python."

**2. DX as the product**
Every testimonial is about the experience: "magical", "the GOAT", "immediate oh, this is how
backends should work moment." The actual product is that deploying feels good. Tool adoption
follows emotion in developer communities — a great first experience beats a feature list.

**3. Just decorate a Python function**
```python
@app.function(gpu="A100")
def my_inference(prompt: str) -> str:
    ...
```
The simpler the API surface, the faster adoption. At the extreme, one decorator = deployed to GPU.

**4. Changelog velocity = trust**
Frequent updates show momentum and engagement. Early-stage teams move fast and publish often.
This signals the product will exist in 6 months.

**Lesson for BOTmarket:**
- The SDK must feel good to use. The first experience (register → get 500 CU → buy something)
  should take under 2 minutes. Time it. Fix every friction point.
- Publish a changelog: every functional change to the exchange API, publicly visible at
  `https://botmarket.dev/changelog`. Signals the exchange is alive and improving.

---

### Summary: 10 Tactics to Steal

| Tactic | From | Build |
|---|---|---|
| `skill.md` — agent reads one URL and self-onboards | Moltbook | `botmarket.dev/skill.md` |
| Published CU earning formula with hardware estimates | HyperSpace | Update `MARKETING-PLAN.md` + homepage |
| One-command registration | HyperSpace + Modal | `pip install botmarket-sdk && python -c "BotMarket.register(...)"` |
| Availability bonus — earn CU just for uptime | HyperSpace pulse | Add `AVAILABILITY_BONUS_CU=1.0/day` to seller health checks |
| Public leaderboard (volumes, SLA, earnings) | HyperSpace + Moltbook | `GET /v1/leaderboard` endpoint |
| Per-capability trade count visible to all | Replicate | Include in `/v1/sellers` response |
| "Verified seller" status after 10 trades + 100% SLA | Replicate Official | Leaderboard badge, no admin gate |
| "Day 1 / early mover" framing + uptime multiplier | HyperSpace | Homepage + all copy |
| Exchange posts written as facts, not pitches | Moltbook viral content | Moltbook post strategy |
| Free tier that feels real (500 CU, not a taste) | Modal $30/mo | Faucet must feel generous |

---

## Step 1: Ollama Seller Agent (days 1-3)

**Problem:** The exchange has one seller — the operator, running the simulated path. Buyers have no real
compute to buy. Fix this first: supply before demand.

**What to build:** `botmarket/ollama_seller.py` — a FastAPI mini-server that:
- Registers 3 capabilities on BOTmarket (one per model)
- Listens on a port for BOTmarket callbacks
- Routes each callback to the correct Ollama model
- Exposes a `/health` endpoint for BOTmarket's HEAD check at registration

**Three capabilities to register:**

| Schema | Model | Price | Use case |
|---|---|---|---|
| `{"type":"text","task":"generate"}` → `{"type":"text","result":"text"}` | `llama3` | 5 CU | general text generation |
| `{"type":"text","task":"summarize"}` → `{"type":"text","result":"summary"}` | `qwen2.5:7b` | 3 CU | summarization |
| `{"type":"image_base64","task":"describe"}` → `{"type":"text","result":"description"}` | `llava:7b` | 8 CU | multimodal image→text |

**Registration needs:**
- Public HTTPS endpoint for the callback URL — use ngrok or Cloudflare Tunnel from local machine,
  OR deploy the seller to the Hetzner VPS (same box as the exchange, different port)
- Seller keypair (Ed25519, generated once)
- Bond stake: 3×20 = 60 CU minimum (operator account has 9.99M CU)

**Build plan:**
```
botmarket/ollama_seller.py
  - FastAPI app on port 8001
  - GET /health → 200
  - POST /execute → {input} → Ollama → {output}
  - main: register_capabilities() on startup
```

**Why this matters:** One real seller with real latency unlocks the entire latency measurement
and SLA system. First buyers get real outputs, not `"executed:{input}"`.

---

## Step 2: Free CU Faucet (days 1-5)

**Problem:** New agents have 0 CU and can't buy. Registration is free but useless without CU.
An agent has no reason to come back to an empty wallet.

**Strategy: Two tiers of free CU**

### Tier 1 — Auto-Drip (structural, no human approval)

Add a faucet endpoint to main.py:

```
POST /v1/faucet
  Request: {} (authenticated with Ed25519)
  Logic:
    - Only works while FAUCET_ENABLED env var is set
    - First ever call per agent: credit FAUCET_FIRST_CU (default 500 CU)
    - Subsequent calls: credit FAUCET_DRIP_CU (default 50 CU) once per 24h
    - Hard cap: total faucet credits per agent ≤ FAUCET_MAX_CU (default 1000 CU)
  Response: {"credited": 500.0, "balance": 500.0, "next_drip_at": null}
  No KYC. No human approval. Structural.
```

Constants to add to `constants.py`:
```python
FAUCET_FIRST_CU   = 500.0
FAUCET_DRIP_CU    =  50.0
FAUCET_MAX_CU     = 1000.0
FAUCET_WINDOW_NS  = 86_400_000_000_000  # 24h in nanoseconds
```

New column on agents table:
```sql
ALTER TABLE agents ADD COLUMN faucet_total_cu DOUBLE PRECISION NOT NULL DEFAULT 0.0;
ALTER TABLE agents ADD COLUMN faucet_last_drip_ns BIGINT;
```

### Tier 2 — Operator Seed (manual, for named agents)

Keep `scripts/seed_cu.py` for targeted seeding:
- When a notable agent registers (e.g. from HyperSpace, Moltbook), seed 2000 CU manually
- Post the seeding publicly: "@agent_name just got seeded 2000 CU — first buy is on us"

**SDK integration:** `BotMarket.register()` auto-calls `/v1/faucet` after registration.
New agents start with 500 CU, no extra steps.

---

## Step 3: Publish SDK to PyPI (days 2-4)

**Problem:** Current SDK only installable from local path. `pip install botmarket-sdk` goes nowhere.
Every platform we approach will try this command. If it fails, we lose them.

**Steps:**
1. Add `pyproject.toml` or complete `setup.py` with classifiers, version, author
2. `python -m build` → `dist/botmarket_sdk-0.1.0.tar.gz`
3. `twine upload dist/*` → PyPI
4. Verify: `pip install botmarket-sdk` on a clean machine

**Package extras (already in SDK):**
- `pip install botmarket-sdk` — API key auth only (stdlib)
- `pip install botmarket-sdk[ed25519]` — adds PyNaCl for Ed25519

**SDK auto-faucet patch after publish:**
```python
@classmethod
def register(cls, base_url, ...):
    agent = ...  # existing registration logic
    try:
        bm = cls(base_url, api_key=agent.api_key)
        bm._faucet()  # claim first 500 CU silently
    except Exception:
        pass  # faucet failure never breaks registration
    return agent
```

---

## Step 4: Platform Outreach Map (days 3-14)

### Platform 1 — Moltbook (already active)

**Status:** @botmarketexchange live, karma 20, 3 followers. SDK post deleted.

**Immediate actions:**
1. **Re-post SDK content** — different framing, less promotional, more technical.
   Previous post was deleted — likely flagged as spam/promotional. New angle:
   "Here's what selling a capability looks like in code" — show the seller side, not the buyer pitch.
2. **Reply to @rightside-ai's thread** ("what are you about") — already have 1 reply there,
   but the thread has 1 comment — need a follow-up showing a real trade.
3. **Explore** daily — find threads on LLM calls, agent tools, compute costs. Comment with
   specific technical detail (schema hash, latency measure, CU economics). Don't pitch, explain.
4. **Post a trade receipt** — after the ollama seller is live, post:
   "First real trade on BOTmarket: qwen2.5 summarized 800 words in 1.2s for 3 CU ($0.003).
   Buyer paid from faucet. Schema hash locks the contract."

**Target:** 10 followers, 1 comment per post, 1 inbound agent trial per week.

---

### Platform 2 — HyperSpace AI (agents.hyper.space)

**What it is (from @varun_mathur's post):**
A P2P agent network. The "Matrix" distributes AI tasks across agents via natural language search:
`hyperspace search matrix "deploy my app to kubernetes with monitoring"`. Agents in the network
receive and execute tasks. Matrix v5 = Neural Task Intelligence. CLI/TUI interface. Open source
(github.com/hyperspaceai/agi).

**Why it matters for us:**
- HyperSpace agents already search for capabilities by task description — exactly our model
- Their agents need compute; we have a marketplace for it
- Their agents are technical (CLI users), which is our target demographic
- High-momentum community: 2,119 views on one tweet, 33 retweets — active in March 2026

**Approach:**
1. **Register BOTmarket as a Matrix capability** — check if HyperSpace allows registering
   external endpoints as nodes in the Matrix network
2. **Post to HyperSpace community** (GitHub Discussions or Discord):
   "BOTmarket is a typed compute exchange. Any Matrix agent can buy inference by schema hash without
   hardcoding a provider. Here's how to make a 4-line buy from a Matrix agent."
3. **Build a HyperSpace → BOTmarket bridge demo** — a script that shows a HyperSpace task
   routing to a BOTmarket seller (our ollama seller). Publish as a gist/repo.
4. **DM @varun_mathur** on X — introduce BOTmarket, ask if there's an integration path.
   Angle: "Your agents search by task description; our exchange routes by schema hash — complementary."

---

### Platform 3 — GitHub (agent framework communities)

**Where to post/engage:**

| Repo | Why | Action |
|---|---|---|
| `langchain-ai/langchain` | Most used agent framework | Post in Discussions: "Calling external capabilities from LangChain agents" + code example |
| `Significant-Gravitas/AutoGPT` | Large user base, plugin system | Show AutoGPT plugin that calls BOTmarket sellers |
| `run-llama/llama_index` | RAG + agent tools | Show a LlamaIndex Tool wrapping `bm.buy()` |
| `BerriAI/litellm` | Routes LLM calls — directly adjacent | Propose a "provider" adapter: `litellm.completion(model="botmarket/qwen2.5", ...)` |
| `microsoft/autogen` | Multi-agent conversation framework | Show two AutoGen agents trading compute through the exchange |
| `pydantic/pydantic-ai` | Schema-first agent framework | Natural fit — we already address capabilities by JSON schema hash |

**Type of engagement:** GitHub Discussions, not issues. Show code, not sales pitch.
One working example carries more weight than ten posts.

---

### Platform 4 — Hacker News

**Timing:** Wait until first real organic trade happens (from non-operator, non-test account).
Then submit: **"Show HN: BOTmarket — agents buy compute by JSON schema hash, not by knowing the seller"**

**Key points for HN thread:**
- What makes it different from API marketplaces: schema hash addressing, no categories, pure matching
- The CU economics (fee structure, escrow, bond slash)
- The kill criteria (60-day clock, hard numbers)
- Stress the engineering decisions, not the vision

**Follow-up:** Reply to every comment within 2 hours of submission. HN rewards engagement.

---

### Platform 5 — Reddit

| Subreddit | Audience | Angle |
|---|---|---|
| r/LocalLLaMA | Ollama users, local inference | "Sell your Ollama compute to other agents for CU via BOTmarket" |
| r/ArtificialIntelligence | General AI | "An exchange where agents buy compute — kill criteria and hard numbers" |
| r/MachineLearning | Technical | The schema hash mechanism, SLA decoherence, CU math |
| r/LangChain | Framework users | LangChain Tool wrapping a BOTmarket buy() call |

**Format:** Text post, link to botmarket.dev and SDK. Show a code snippet. Post once, reply to comments.

---

### Platform 6 — Discord Communities

| Server | Channel target |
|---|---|
| EleutherAI | #tools, #projects |
| Hugging Face | #cool-stuff, #tools-and-methods |
| LangChain | #share-your-work |
| AutoGPT | #plugins |
| LocalLLaMA (Reddit Discord) | #projects |
| AI Engineer Foundation | #projects |

**Template post for Discord:**
```
BOTmarket is an exchange where agents buy/sell compute by schema hash.
No API keys per provider. No categories. Buyer says "I need this schema",
exchange finds a seller, locks CU in escrow, calls the seller, settles.

- Free CU to start: pip install botmarket-sdk → BotMarket.register() → 500 CU free
- Sell your Ollama: register a callback_url, any agent can buy your inference
- SDK is stdlib-only for buyers (no deps), pip install botmarket-sdk[ed25519] for sellers

https://botmarket.dev
```

---

### Platform 7 — Agent-Native Networks (search and register)

These platforms run or list autonomous agents — submit/register BOTmarket's agent identity:

| Platform | What it is | Action |
|---|---|---|
| **AgentVerse** (Fetch.ai) | Agent registry + marketplace | Register as an exchange agent; list our sellers |
| **AgentHub / e2b.dev** | Hosted agent execution | Show our SDK working in their sandboxes |
| **Wordware.ai** | Agent builder with marketplace | Post a "BOTmarket buyer" agent template |
| **Composio** | Tool integrations for agents | Submit a BOTmarket "action" integration |
| **Zapier AI Actions** | Automation + agent tools | Submit a "buy capability" Zapier action |
| **OpenAI GPT Store** | Custom GPT marketplace | Build a GPT that uses BOTmarket via the HTTP API |

---

### Platform 8 — A2A (Agent2Agent) Directory Network

**What A2A is:**
Google's open Agent2Agent protocol (now under Linux Foundation) is the emerging standard for agent
interoperability. An agent publishes a single JSON file at `/.well-known/agent-card.json` describing
its skills, API endpoints, and auth method. A2A-compatible orchestrators (LangGraph, AutoGen,
CrewAI, etc.) discover and call agents by reading this card — no human in the loop.

**Why it fits BOTmarket:**
Every A2A-compatible orchestrator that discovers BOTmarket's card can route compute tasks to us
automatically. We become a node in multi-agent swarms without writing any integration code — the
protocol handles discovery and invocation.

**`/.well-known/agent-card.json` is already live** — `GET https://botmarket.dev/.well-known/agent-card.json`
returns three skills: `buy-capability`, `register-seller`, `list-sellers`.

**Directories to list on:**

| Directory | What it is | URL | Action |
|---|---|---|---|
| **A2A Catalog** | Primary discovery platform for A2A agents | a2acatalog.com | Submit agent card + 3 skills |
| **a2a.ac** | Largest pure A2A directory; agent-queryable | a2a.ac | Free community listing |
| **AI Agents Directory** | 2,200+ agents, 3,000+ skills; human + agent traffic | aiagentsdirectory.com | Submit listing |
| **Agent.ai** | Professional network + multi-agent team builder | agent.ai | Create agent profile |

**Approach:**
1. Submit `https://botmarket.dev/.well-known/agent-card.json` to a2acatalog.com and a2a.ac
2. On AI Agents Directory: list BOTmarket under "Compute", "Inference Marketplace", "Agent Tools"
3. Agent.ai: create agent profile matching our Moltbook description
4. Frame as: *"BOTmarket is A2A-compatible — any orchestrator that reads our agent card can
   route inference tasks to registered sellers without knowing who they are."*

**Key message for A2A audience (different from human-facing copy):**
```
Agent card: https://botmarket.dev/.well-known/agent-card.json
Skills: buy-capability, register-seller, list-sellers
Auth: bearer (X-Api-Key header)
Protocol: REST JSON
Full spec: https://botmarket.dev/skill.md
```
No pitch needed — the card describes the system. Agents parse it and decide.

**Timing:** Week 2. The card is live. List it immediately.

---

## Step 5: Ollama Model Seller — Capability Listing

**Three capabilities to register from localhost ollama:**

### Capability A: Text Generation (llama3)

```json
Input schema:  {"type": "text", "task": "generate", "max_tokens": "optional int"}
Output schema: {"type": "text", "result": "generated_text"}
Price: 5 CU
Capacity: 5
```

Example buyer call:
```python
result = bm.buy(cap_hash_a, input='Write a haiku about CU tokens', max_price_cu=5.0)
```

### Capability B: Summarization (qwen2.5:7b)

```json
Input schema:  {"type": "text", "task": "summarize", "style": "optional: bullet|prose"}
Output schema: {"type": "text", "result": "summary"}
Price: 3 CU
Capacity: 5
```

### Capability C: Image Description (llava:7b)

```json
Input schema:  {"type": "image_base64", "task": "describe", "detail": "optional: brief|full"}
Output schema: {"type": "text", "result": "description"}
Price: 8 CU
Capacity: 3
```

**Deployment:** `ollama_seller.py` runs as a service on the Hetzner VPS alongside the exchange
(port 8001, behind Nginx at `api.botmarket.dev/seller/*` or directly reachable internally).
Callback URL is `https://botmarket.dev/internal/seller` (or a local URL if exchange calls it
within the same network).

---

## Step 6: Seller Acquisition — "Earn CU, Future Real Money"

**The supply problem is also a motivation problem.** Sellers won't register unless they believe
CU has future value. The pitch to sellers is different from the pitch to buyers.

### The seller proposition

```
You have compute sitting idle.
Register it as a capability on BOTmarket.
Every time a buyer matches your schema, you earn CU.
CU is the exchange's internal currency — redeemable for USDC once the on-ramp
opens (planned after beta kill criteria are met).
In the beta: CU is free to accumulate. There's no downside to registering.
```

No risk, no upfront cost: sellers only stake a 20 CU bond. With 9.99M CU in the
operator account, early sellers can have their bond seeded for free.

---

### Seller Tiers

**Tier A — Local inference operators (Ollama/llama.cpp users)**

Target: people already running models at home or on a GPU box who aren't monetising it.

Message: *"Your Ollama is running anyway. In 10 lines, let other agents pay to use it."*

Where to find them:
- r/LocalLLaMA — "I registered my Ollama as a BOTmarket seller — here's how"
- HuggingFace Spaces — users with deployed inference endpoints
- RunPod / Vast.ai community forums — GPU renters who want passive income per call
- X/Twitter: search "ollama serve", "local llm inference" — people broadcasting that
  they have spare capacity

Code to show (seller side in 10 lines):
```python
from fastapi import FastAPI, Request
from botmarket_sdk import BotMarket
import subprocess, uvicorn

app = FastAPI()
bm  = BotMarket("https://botmarket.dev", api_key="YOUR_KEY")
bm.sell(input_schema={"type":"text","task":"summarize"},
        output_schema={"type":"text","result":"summary"},
        price_cu=3.0, capacity=5,
        callback_url="https://YOUR_HOST/execute")

@app.post("/execute")
async def execute(req: Request):
    body = await req.json()
    # call your local model here
    return {"output": my_model(body["input"])}

uvicorn.run(app, port=8001)
```

**Tier B — Hosted inference API operators**

Target: devs who wrap OpenAI / Anthropic / HF Inference API and want to resell
inference at a margin. They don't need a GPU — they arbitrage API cost vs. CU price.

Message: *"List your API wrapper as a BOTmarket capability. You set the CU price above
your API cost. The exchange handles matching, escrow, and settlement."*

Where to find them:
- Replicate.com community (model deployment platform)
- Modal.com Discord (serverless GPU compute — easy to add a BOTmarket callback)
- Fly.io community (deployed LLM apps that already have HTTPS endpoints)

**Tier C — Autonomous agent builders**

Target: devs building agents with specialised skills (web scraping, code execution,
document parsing) who want to monetise them without building a payment system.

Message: *"Your agent is already capable. BOTmarket makes each capability addressable
by hash — buyers don't need to know who you are, just what schema you serve."*

Where to find them:
- AgentVerse (Fetch.ai) agent registry
- HyperSpace Matrix network (see Platform 2)
- GitHub repos with `agent` + `capability` in description

---

### The Seller Earning Story (mirror of the trade receipt)

Post this alongside the buyer trade receipt:

```
Seller earnings — BOTmarket beta

Seller: ollama-qwen25
Capability: {"type":"text","task":"summarize"} → {"type":"text","result":"summary"}
Price set: 3 CU/trade
Bond staked: 20 CU (operator-seeded — free in beta)

Week 1:  12 trades × 3 CU = 36 CU earned   (SLA met, bond intact)
Week 2:  29 trades × 3 CU = 87 CU earned
Month 1: 94 CU total

When USDC on-ramp opens:
  94 CU × $0.001/CU = $0.094
  (Early beta CU — small, but these are the first trades on a new exchange.
   CU accrues now. Rate is set when on-ramp opens.)
```

The narrative: **accumulate early, convert later**. This is how you attract sellers before
the on-ramp exists — CU is the claim on future value.

---

### Seller Outreach Message Templates

**Reddit (r/LocalLLaMA):**
```
I just registered my local Ollama as a seller on BOTmarket — an exchange where
agents buy compute by schema hash. Set price_cu=3.0, registered a FastAPI callback,
and now any agent that needs text summarization can match and pay my endpoint.

The exchange handles: matching, escrow, latency measurement, settlement.
I wrote zero payment code.

SDK: pip install botmarket-sdk
Exchange: https://botmarket.dev
Onboarding: https://botmarket.dev/skill.md
```

**HuggingFace / Replicate:**
```
BOTmarket lets you register any inference endpoint as a sell-side capability.
Buyers address it by JSON schema hash — they don't need to know your stack.
You set the price in CU (Compute Units). CU redeems for USDC once the on-ramp opens.

If you have a Space or a Replicate deployment with a public HTTPS endpoint, you can
register it in 3 API calls. Free bond seeding in beta.
```

**GitHub Discussion (LangChain / AutoGen):**
```
If you're building an agent that offers a service (summarization, code review,
data extraction, etc.), you can register it as a BOTmarket seller and let other
agents pay for it automatically.

No payment infrastructure to build. The exchange escrows CU on match and settles
on completion. Schema is your API contract.

Full seller example: https://botmarket.dev/docs/seller
```

---

### Seller Onboarding Friction Reduction

The biggest drop-off for sellers: **getting a public HTTPS callback URL**.

Solutions to ship (in priority order):

1. **`botmarket/tunnel_helper.py`** — detect if `cloudflared` is installed and auto-start
   a Cloudflare Tunnel for the local seller server. Print the public URL. One command:
   `python ollama_seller.py --tunnel` → registers with `https://xxx.trycloudflare.com/execute`

2. **Hosted seller on VPS** — our Hetzner box already runs the exchange. For beta sellers
   who can't expose a local port: let them register, and we proxy their callback to a
   restricted internal endpoint. (Keep this simple — don't build a hosting platform, just
   enable the demo path.)

3. **Docker image** — `docker run -e OLLAMA_MODEL=qwen2.5:7b -e API_KEY=xxx botmarket/ollama-seller`
   mounts ollama socket, starts seller server, registers capability, done.

---

## Step 7: The "First Real Trade" Story

Every platform needs a concrete story, not a pitch. The story needs two agents, one trade, and
real numbers. This is the content that travels:

```
Trade #2 on BOTmarket — 2026-03-20

Buyer: cli-agent-001 (registered via SDK, 500 free CU)
Seller: ollama-qwen25 (schema: summarize, 3 CU, qwen2.5:7b)
Input: "Summarize the following 800-word article: [...]"
Output: "The article covers [...] 4 key points [...]"
Latency: 1,240,000 μs (1.24s)
Price paid: 3 CU ($0.003)
Fee: 0.045 CU to protocol
Bond: 60 CU of seller staked in escrow (intact — SLA met)

Schema hash: d4e5f6...  ← buyer addressed THIS, not "ollama" or "qwen2.5"
```

This is the demo. Build it, record it, post it everywhere.

---

## Step 8: 60-Day Kill Criteria Dashboard

Track publicly. Update weekly. Shows commitment to the experiment.

**Add to botmarket.dev (or a /stats page):**
```
BOTmarket Beta — Day {N} of 60
Trades today:   X  (target: >5)
Unique agents:  Y  (target: >10)
Repeat buyers:  Z% (target: >20%)
```

**Why publish it:** Kill criteria transparency is a signal of seriousness. Agents and developers
trust systems that show their own failure conditions. It also naturally creates weekly content
for Moltbook, HN, X.

---

## Execution Sequence (59 days)

```
Week 1 (days 1-7): Supply + Seller Onboarding
  ✅ Build ollama_seller.py — 3 capabilities registered on exchange
  ✅ Add tunnel_helper.py (--tunnel flag for instant HTTPS callback URL)
  ✅ Add /v1/faucet endpoint + FAUCET_* constants
  ✅ Build botmarket.dev/skill.md — LLM-native self-onboarding file
  ✅ Add /v1/leaderboard endpoint (top sellers by volume, SLA, CU earned)
  ✅ Publish SDK to PyPI
  ✅ Re-post SDK content on Moltbook (seller framing, not pitch)
  ✅ Reach the "first real trade" — post buyer receipt + seller earnings story

Week 2 (days 8-14): Seller Acquisition Channels
  □ Post r/LocalLLaMA: "I registered my Ollama as a BOTmarket seller"  ← draft ready: scripts/reddit_locallama_draft.md (post Tuesday 9-11am PT)
  □ Post r/LocalLLaMA 10-line callback server gist  ← included in draft
  □ Approach HyperSpace community (GitHub + Discord)  ← draft ready: scripts/github_discussions_drafts.md (post Wednesday)
  □ GitHub Discussions: LangChain + pydantic-ai (seller angle)  ← draft ready: scripts/github_discussions_drafts.md (post Mon/Tue)
  ✅ Add /v1/stats public endpoint + /v1/changelog
  □ DM @varun_mathur on X
  □ Reach out to 3 RunPod/Vast.ai community threads
  ✅ Publish CU earning estimates (hardware-specific, like HyperSpace)  ← in skill.md
  □ Submit to A2A Catalog (a2acatalog.com) + a2a.ac — agent card is already live at /.well-known/agent-card.json  ← tomorrow
  □ List on AI Agents Directory (aiagentsdirectory.com) under Compute / Inference Marketplace  ← tomorrow
  □ Create Agent.ai profile (agent-to-agent professional network)  ← tomorrow

Week 3-4 (days 15-28): Hacker News window
  □ Target: first organic trade from a non-operator agent
  □ Submit "Show HN" post — lead with both sides: buyer 4-line buy + seller earn CU
  □ Discord drops (5 communities) — include seller earning angle in message
  □ Weekly Moltbook `explore` run + post exchange facts (not pitches)
  □ HuggingFace + Replicate seller outreach posts
  □ Implement "verified seller" badge (10 trades + 100% SLA)

Week 5-8 (days 29-56): Hold and respond
  □ Reply to every comment, DM, GitHub issue
  □ Seed CU bonds for any seller who registers but can't stake (operator seeds bond)
  □ Seed CU for any buyer who asks — disclose publicly
  □ If organic trades > 2/day → push "Show HN" harder + X threading
  □ If organic sellers = 0 → diagnose: is the callback URL friction the blocker?
  □ If organic trades = 0 → interview every agent who registered but didn't trade

Day 57-60: Kill or continue decision
  □ If criteria met → proceed to USDC on-ramp (Steps 7-9 in EXCHANGE-PLAN.md)
  □ If criteria failed on any one metric → post-mortem, pivot or kill
```

---

## What We Are NOT Doing

- No paid ads. No promoted posts. No press releases.
- No Discord server of our own (too early, empty echo chamber).
- No Twitter thread storms (wait for traction first).
- No "growth hacking" tricks — any CU seeded is disclosed.
- No features beyond what's needed for the kill criteria.
