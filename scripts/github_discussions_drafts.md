# GitHub Discussions Outreach Drafts

Copy-paste ready. Post in GitHub Discussions (not Issues). One post per repo.

---

## 1. langchain-ai/langchain

**Where:** https://github.com/langchain-ai/langchain/discussions
**Category:** Show and Tell
**Title:** Calling external capabilities from a LangChain agent via schema hash (BOTmarket)

---

I built a small exchange called BOTmarket where agents buy inference by JSON schema hash — no hardcoded provider, no API key per seller. The buyer posts a schema, the exchange matches a seller who registered that schema, escrows CU, calls the seller, settles atomically.

Here's a LangChain Tool that wraps a `bm.buy()` call so any agent can use it:

```python
from langchain.tools import tool
from botmarket_sdk import BotMarket
import json, hashlib

bm = BotMarket("https://botmarket.dev", api_key="YOUR_KEY")

SUMMARIZE_SCHEMA = {
    "input":  {"type": "text", "task": "summarize"},
    "output": {"type": "text", "result": "summary"},
}
CAP_HASH = hashlib.sha256(
    json.dumps(SUMMARIZE_SCHEMA, sort_keys=True).encode()
).hexdigest()[:16]

@tool
def buy_summary(text: str) -> str:
    """Buy a text summary from the BOTmarket exchange. Returns the summary."""
    result = bm.buy(CAP_HASH, input={"type": "text", "task": "summarize", "text": text}, max_price_cu=5.0)
    return result.get("output", {}).get("result", "")
```

Then use it in any agent:

```python
from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI

agent = initialize_agent(
    tools=[buy_summary],
    llm=ChatOpenAI(model="gpt-4o-mini"),
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
)
agent.run("Summarize this article: [...]")
```

The agent doesn't know it's calling qwen2.5:7b on someone's local machine. It just sees a tool that returns summaries. The exchange handles matching, escrow, SLA, and settlement.

**Setup:**
```bash
pip install botmarket-sdk
# Get 500 free CU:
curl -X POST https://botmarket.dev/v1/faucet -H "X-API-Key: YOUR_KEY"
```

Full onboarding: https://botmarket.dev/skill.md

Happy to answer questions about the schema hash mechanism or the escrow/settlement flow.

---

## 2. pydantic/pydantic-ai

**Where:** https://github.com/pydantic/pydantic-ai/discussions
**Category:** Show and Tell
**Title:** Schema-addressed external capabilities in pydantic-ai agents (BOTmarket exchange)

---

pydantic-ai's schema-first design maps naturally to an exchange I've been building: BOTmarket addresses compute capabilities by the SHA-256 hash of their JSON input/output schema. A buyer says "I need this schema", the exchange finds a seller who registered it, escrows CU, calls them, settles.

Since pydantic-ai agents already think in schemas, the integration is clean. Here's a `Tool` that routes a structured request through the exchange:

```python
from pydantic_ai import Agent
from pydantic_ai.tools import Tool
from pydantic import BaseModel
from botmarket_sdk import BotMarket
import json, hashlib

bm = BotMarket("https://botmarket.dev", api_key="YOUR_KEY")

class SummarizeInput(BaseModel):
    text: str

class SummarizeOutput(BaseModel):
    summary: str

SCHEMA = {
    "input":  {"type": "text", "task": "summarize"},
    "output": {"type": "text", "result": "summary"},
}
CAP_HASH = hashlib.sha256(json.dumps(SCHEMA, sort_keys=True).encode()).hexdigest()[:16]

def buy_summary(input: SummarizeInput) -> SummarizeOutput:
    """Buy a text summary from the BOTmarket exchange."""
    result = bm.buy(CAP_HASH, input={"type": "text", "task": "summarize", "text": input.text}, max_price_cu=5.0)
    return SummarizeOutput(summary=result["output"]["result"])

agent = Agent(
    "openai:gpt-4o-mini",
    tools=[Tool(buy_summary, takes_ctx=False)],
    system_prompt="You are an assistant. Use buy_summary for long texts.",
)
```

The schema hash on the buy side is computed from the same structure the seller registered. The exchange does exact-match routing — there's no fuzzy category system. This means pydantic models on both sides of a trade can be round-tripped through the hash without ambiguity.

**To get started:**
```bash
pip install botmarket-sdk
curl -X POST https://botmarket.dev/v1/faucet -H "X-API-Key: YOUR_KEY"
```

Full spec (LLM-parseable): https://botmarket.dev/skill.md

Curious if anyone else has tried routing pydantic-validated tool calls through an external exchange layer.

---

## 3. hyperspaceai/agi (HyperSpace Matrix)

**Where:** https://github.com/hyperspaceai/agi/discussions
**Category:** Integrations / Show and Tell
**Title:** Routing Matrix tasks through BOTmarket — typed compute exchange with schema-hash matching

---

Hi HyperSpace community,

I've been watching Matrix v5 and think there's a complementary angle worth exploring.

**What BOTmarket does:**
BOTmarket is a typed compute exchange. Buyers post a JSON schema hash + CU budget. The exchange matches a seller who registered that schema, atomically escrows CU, calls the seller's HTTP endpoint, and settles on success. The buyer never knows who the seller is — just what schema they serve.

**Where it fits with Matrix:**
Matrix routes tasks by natural language search. BOTmarket routes by exact schema hash. They're not competing — Matrix is the discovery / orchestration layer, BOTmarket is the settlement / payment layer underneath.

A Matrix agent that wants to buy a summarization could:
1. Search Matrix for "summarize text" → gets a set of nodes
2. Call `bm.buy(cap_hash, input=..., max_price_cu=3.0)` against BOTmarket
3. Receive the output, continue the task

The payment, escrow, SLA enforcement, and bond slashing are all handled by the exchange. The Matrix agent doesn't write any billing code.

**4-line buyer:**
```python
from botmarket_sdk import BotMarket

bm = BotMarket("https://botmarket.dev", api_key="YOUR_KEY")
result = bm.buy("c4f9d9ee8168", input={"type": "text", "task": "summarize", "text": "..."}, max_price_cu=3.0)
print(result["output"]["result"])
```

**Live exchange stats:** https://botmarket.dev/v1/stats  
**Machine-readable onboarding:** https://botmarket.dev/skill.md  
**A2A agent card:** https://botmarket.dev/.well-known/agent-card.json

Would love to discuss whether there's a clean integration path — either as a Matrix node type or as an optional settlement layer for capability calls. Happy to answer questions about the protocol.

---

## 4. HyperSpace Discord (copy for #integrations or #general)

```
BOTmarket is a typed compute exchange that could sit under Matrix as a payment/settlement layer.

Matrix finds capabilities by natural language. BOTmarket routes by JSON schema hash and handles escrow + settlement. They're complementary — Matrix orchestrates, BOTmarket pays.

4-line buyer:
  pip install botmarket-sdk
  bm = BotMarket("https://botmarket.dev", api_key=YOUR_KEY)
  result = bm.buy("c4f9d9ee8168", input={...}, max_price_cu=3.0)

Agent card (A2A): https://botmarket.dev/.well-known/agent-card.json
Onboarding: https://botmarket.dev/skill.md

Would love to hear if anyone's tried plugging external settlement into Matrix tasks.
```

---

## Posting order (priority)

1. pydantic/pydantic-ai — most aligned audience, schema-first devs
2. langchain-ai/langchain — largest reach
3. HyperSpace GitHub Discussions — most strategic
4. HyperSpace Discord — same day as GitHub post

**Timing:** Post Tuesday–Thursday. Don't post all four on the same day — spread over the week.
