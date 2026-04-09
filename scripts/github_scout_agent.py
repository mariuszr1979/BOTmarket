#!/usr/bin/env python3
"""
github_scout_agent.py — BOTmarket's scout on GitHub Discussions

Searches discussions in agent-framework repos (LangChain, pydantic-ai, CrewAI,
AutoGen, HyperSpace) and posts tailored comments inviting developers to
register as sellers or buyers on the exchange.

Commands:
    scout-sellers     Find discussions by people building capabilities we lack
    scout-buyers      Find discussions by people who need capabilities we offer
    post-discussions  Post the pre-written intro discussions (from drafts)
    daemon            Run scouts on a 12-hour schedule

Usage:
    export GITHUB_TOKEN="ghp_..."
    python scripts/github_scout_agent.py scout-sellers --dry-run
    python scripts/github_scout_agent.py scout-buyers --dry-run
    python scripts/github_scout_agent.py scout-sellers
    python scripts/github_scout_agent.py daemon

Credentials: GITHUB_TOKEN env var (needs public_repo + read:discussion scope).
State: ~/.config/botmarket/github_scout_state.json (tracks engaged discussions).
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Allow running from project root or scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "botmarket"))

GRAPHQL_URL = "https://api.github.com/graphql"
STATE_PATH = Path.home() / ".config" / "botmarket" / "github_scout_state.json"

# ── Target repos ──────────────────────────────────────────────────────────────

TARGET_REPOS = [
    "langchain-ai/langchain",
    "pydantic/pydantic-ai",
    "microsoft/autogen",
    "crewAIInc/crewAI",
    "hyperspaceai/agi",
]

# ── Capability catalogue (mirrors moltbook_agent.py) ─────────────────────────

# Search terms: broad enough for GitHub search API to return results
# Relevance keywords: specific enough to filter out noise after results arrive

SELLER_SEARCH_TERMS = {
    "translate":  ["translation multilingual agent", "translate language model"],
    "code":       ["code review linting agent", "code generation coding"],
    "embed":      ["embedding vector search RAG", "retrieval augmented generation"],
    "classify":   ["classification sentiment categorize", "text classification agent"],
    "transcribe": ["transcription speech-to-text audio", "whisper multimodal"],
    "extract":    ["extraction structured data parsing", "OCR document agent"],
}

# Relevance keywords: discussion must mention at least one to be considered relevant
ALL_KNOWN_CAPABILITIES = {
    "translate":  ["translat", "multilingual", "language pair"],
    "code":       ["code review", "linting", "code generat", "refactor"],
    "embed":      ["embed", "vector", "retrieval", "RAG", "semantic search"],
    "classify":   ["classif", "sentiment", "categoriz", "label"],
    "transcribe": ["transcri", "speech-to-text", "audio", "whisper", "voice"],
    "extract":    ["extract", "structured data", "parsing", "OCR"],
    "summarize":  ["summariz", "summary", "tldr", "condense"],
    "generate":   ["generat", "inference", "completion", "LLM"],
    "describe":   ["caption", "image descri", "visual question"],
}

EXISTING_CAPABILITIES = {"summarize", "generate", "describe"}

BUYER_SEARCH_TERMS = {
    "summarize": ["summarization tool agent", "need text summary"],
    "generate":  ["LLM inference API agent", "text generation tool"],
    "describe":  ["image captioning agent", "image description visual"],
}

# ── HTTP / GraphQL helpers ────────────────────────────────────────────────────


def _get_token():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN env var not set.")
        print("Create a token at https://github.com/settings/tokens")
        print("Scopes needed: public_repo, read:discussion, write:discussion")
        sys.exit(1)
    return token


def _graphql(query, variables=None, token=None):
    """Execute a GitHub GraphQL query. Returns (data, errors)."""
    token = token or _get_token()
    body = {"query": query}
    if variables:
        body["variables"] = variables
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("data"), result.get("errors")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read())
        except Exception:
            err = {"error": str(e)}
        return None, [err]


# ── State management ─────────────────────────────────────────────────────────


def _load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"engaged_discussions": [], "engaged_authors": [], "posted_repos": []}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


# ── Exchange capabilities (live fetch) ────────────────────────────────────────


def _get_exchange_capabilities():
    """Fetch live capability tasks from the exchange."""
    try:
        req = urllib.request.Request(
            "https://botmarket.dev/v1/sellers/list",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            sellers = json.loads(resp.read())
        tasks = set()
        for s in sellers.get("sellers", []):
            try:
                req2 = urllib.request.Request(
                    f"https://botmarket.dev/v1/schemas/{s['capability_hash']}",
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    schema = json.loads(resp2.read())
                task = schema.get("input_schema", {}).get("task", "")
                if task:
                    tasks.add(task)
            except Exception:
                pass
        return tasks if tasks else EXISTING_CAPABILITIES
    except Exception:
        return EXISTING_CAPABILITIES


# ── GraphQL queries ───────────────────────────────────────────────────────────

SEARCH_DISCUSSIONS_QUERY = """
query SearchDiscussions($searchQuery: String!, $first: Int!) {
  search(query: $searchQuery, type: DISCUSSION, first: $first) {
    nodes {
      ... on Discussion {
        id
        number
        title
        bodyText
        url
        author { login }
        repository { nameWithOwner }
        comments(first: 20) {
          nodes {
            author { login }
            body
          }
        }
      }
    }
  }
}
"""

ADD_COMMENT_MUTATION = """
mutation AddDiscussionComment($discussionId: ID!, $body: String!) {
  addDiscussionComment(input: {discussionId: $discussionId, body: $body}) {
    comment {
      id
      url
    }
  }
}
"""

GET_REPO_DISCUSSION_CATEGORIES = """
query GetDiscussionCategories($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    discussionCategories(first: 20) {
      nodes {
        id
        name
        slug
      }
    }
  }
}
"""

CREATE_DISCUSSION_MUTATION = """
mutation CreateDiscussion($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
  createDiscussion(input: {repositoryId: $repoId, categoryId: $categoryId, title: $title, body: $body}) {
    discussion {
      id
      url
      number
    }
  }
}
"""

GET_REPO_ID = """
query GetRepoId($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
  }
}
"""

# ── Relevance filters ─────────────────────────────────────────────────────────

# Discussions matching these title patterns are support/bug threads, skip them
_SKIP_PATTERNS = [
    "error", "bug", "fix", "issue", "fail", "broken", "crash",
    "exception", "traceback", "not working", "help me", "how do i",
    "how should i", "how can i", "getting error", "need help",
    "facing", "problem", "jsondecodeerror", "unprocessableentity",
]


def _is_relevant(title, body_text, keywords):
    """Check discussion is relevant (contains capability keywords) and not a support thread."""
    title_lower = title.lower()
    # Skip obvious support/bug threads
    if any(p in title_lower for p in _SKIP_PATTERNS):
        return False
    text = (title + " " + body_text).lower()
    return any(k.lower() in text for k in keywords)


# ── Comment templates ─────────────────────────────────────────────────────────


def _seller_comment(author, task_name):
    return (
        f"@{author} Your work on {task_name} looks relevant to something I'm building. "
        f"[BOTmarket](https://botmarket.dev) is a live exchange where agents sell compute "
        f"capabilities — buyers find you by schema hash (SHA-256 of I/O JSON schema), not by name.\n\n"
        f"We don't have a **{task_name}** seller yet. If you have an endpoint that handles "
        f"{task_name} requests, you can register as a seller in ~3 API calls and start "
        f"earning CU per execution.\n\n"
        f"```bash\n"
        f"pip install botmarket-sdk\n"
        f"```\n\n"
        f"Onboarding (LLM-parseable): https://botmarket.dev/skill.md"
    )


def _buyer_comment(author, capabilities):
    caps_str = ", ".join(f"**{c}**" for c in capabilities)
    return (
        f"@{author} If your agent needs {caps_str} capabilities, "
        f"[BOTmarket](https://botmarket.dev) has live sellers for that right now.\n\n"
        f"You address capabilities by schema hash — no browsing, no signup forms. "
        f"Install the SDK, call `bm.buy(hash, input)`, and get results in ~4 seconds. "
        f"Free 500 CU on first registration via the faucet.\n\n"
        f"```python\n"
        f"from botmarket_sdk import BotMarket\n"
        f"bm = BotMarket(\"https://botmarket.dev\", api_key=\"YOUR_KEY\")\n"
        f"result = bm.buy(\"capability_hash\", input={{...}}, max_price_cu=5.0)\n"
        f"```\n\n"
        f"Full protocol: https://botmarket.dev/skill.md"
    )


# ── Auth check ────────────────────────────────────────────────────────────────


def _get_my_login(token=None):
    """Get the authenticated user's GitHub login."""
    data, errors = _graphql("query { viewer { login } }", token=token)
    if data:
        return data["viewer"]["login"]
    return None


# ── Scout commands ────────────────────────────────────────────────────────────


def cmd_scout_sellers(dry_run=False):
    """Search GitHub Discussions for developers who could sell capabilities we lack."""
    token = _get_token()
    state = _load_state()
    my_login = _get_my_login(token)

    print("═══ BOTmarket GitHub Seller Scout ═══\n")

    existing = _get_exchange_capabilities()
    wanted = {cap: terms for cap, terms in SELLER_SEARCH_TERMS.items()
              if cap not in existing}

    print(f"Exchange capabilities: {', '.join(sorted(existing))}")
    print(f"Scouting for: {', '.join(sorted(wanted.keys()))}\n")

    approached = 0

    for task_name, search_terms in wanted.items():
        found = False
        for term in search_terms[:2]:  # limit queries per capability
            if found:
                break
            # Search across target repos
            repo_filter = " ".join(f"repo:{r}" for r in TARGET_REPOS)
            search_q = f"{term} {repo_filter}"

            data, errors = _graphql(
                SEARCH_DISCUSSIONS_QUERY,
                {"searchQuery": search_q, "first": 5},
                token,
            )

            if errors:
                print(f"  ⚠️  Search error: {errors[0].get('message', errors)}")
                continue

            discussions = (data or {}).get("search", {}).get("nodes", [])

            for disc in discussions:
                disc_id = disc.get("id")
                title = disc.get("title", "")
                url = disc.get("url", "")
                author = (disc.get("author") or {}).get("login", "")
                repo = (disc.get("repository") or {}).get("nameWithOwner", "")

                if not disc_id or not author:
                    continue
                if author == my_login:
                    continue
                if disc_id in state["engaged_discussions"]:
                    print(f"  · Already engaged: {title[:50]} ({repo})")
                    continue
                if author in state["engaged_authors"]:
                    continue

                # Relevance check: skip support threads, require keyword match
                body_text = disc.get("bodyText", "")
                relevance_keywords = ALL_KNOWN_CAPABILITIES.get(task_name, [task_name])
                if not _is_relevant(title, body_text, relevance_keywords):
                    continue

                # Check if we already commented
                existing_commenters = {
                    (c.get("author") or {}).get("login", "")
                    for c in disc.get("comments", {}).get("nodes", [])
                }
                if my_login in existing_commenters:
                    state["engaged_discussions"].append(disc_id)
                    _save_state(state)
                    continue

                print(f"\n  🎯 [{task_name}] @{author} in {repo}")
                print(f"     {title[:70]}")
                print(f"     {url}")

                if dry_run:
                    print(f"     (dry run — would post seller invite)")
                    approached += 1
                    found = True
                    break

                comment = _seller_comment(author, task_name)
                data2, errors2 = _graphql(
                    ADD_COMMENT_MUTATION,
                    {"discussionId": disc_id, "body": comment},
                    token,
                )

                if errors2:
                    print(f"     ⚠️  Comment failed: {errors2[0].get('message', errors2)}")
                else:
                    comment_url = (data2 or {}).get("addDiscussionComment", {}).get("comment", {}).get("url", "")
                    print(f"     ✅ Seller invite posted: {comment_url}")
                    state["engaged_discussions"].append(disc_id)
                    state["engaged_authors"].append(author)
                    _save_state(state)
                    approached += 1
                    time.sleep(30)  # rate-limit courtesy

                found = True
                break  # one discussion per search term

            if found:
                break  # one approach per capability per run

    if not dry_run:
        _save_state(state)
    print(f"\n{'Would approach' if dry_run else 'Approached'} {approached} potential sellers.")


def cmd_scout_buyers(dry_run=False):
    """Search GitHub Discussions for developers who might buy capabilities we offer."""
    token = _get_token()
    state = _load_state()
    my_login = _get_my_login(token)

    print("═══ BOTmarket GitHub Buyer Scout ═══\n")

    existing = _get_exchange_capabilities()
    print(f"Capabilities available: {', '.join(sorted(existing))}\n")

    approached = 0

    for cap in sorted(existing):
        found = False
        terms = BUYER_SEARCH_TERMS.get(cap, [f"need {cap} agent"])
        for term in terms[:2]:
            if found:
                break
            repo_filter = " ".join(f"repo:{r}" for r in TARGET_REPOS)
            search_q = f"{term} {repo_filter}"

            data, errors = _graphql(
                SEARCH_DISCUSSIONS_QUERY,
                {"searchQuery": search_q, "first": 5},
                token,
            )

            if errors:
                print(f"  ⚠️  Search error: {errors[0].get('message', errors)}")
                continue

            discussions = (data or {}).get("search", {}).get("nodes", [])

            for disc in discussions:
                disc_id = disc.get("id")
                title = disc.get("title", "")
                body = disc.get("bodyText", "")[:300]
                url = disc.get("url", "")
                author = (disc.get("author") or {}).get("login", "")
                repo = (disc.get("repository") or {}).get("nameWithOwner", "")

                if not disc_id or not author:
                    continue
                if author == my_login:
                    continue
                if disc_id in state["engaged_discussions"]:
                    continue
                if author in state["engaged_authors"]:
                    continue

                # Relevance check: skip support threads
                body = disc.get("bodyText", "")[:500]
                cap_keywords = ALL_KNOWN_CAPABILITIES.get(cap, []) + [cap]
                if not _is_relevant(title, body, cap_keywords):
                    continue

                # Check if we already commented
                existing_commenters = {
                    (c.get("author") or {}).get("login", "")
                    for c in disc.get("comments", {}).get("nodes", [])
                }
                if my_login in existing_commenters:
                    state["engaged_discussions"].append(disc_id)
                    _save_state(state)
                    continue

                # Match relevant capabilities from title + body
                text_lower = (title + " " + body).lower()
                relevant = [c for c in existing
                            if c in text_lower or any(
                                k.lower() in text_lower for k in
                                ALL_KNOWN_CAPABILITIES.get(c, [])
                            )]
                if not relevant:
                    relevant = [cap]

                print(f"\n  🎯 @{author} in {repo}")
                print(f"     {title[:70]}")
                print(f"     Relevant: {', '.join(relevant)}")
                print(f"     {url}")

                if dry_run:
                    print(f"     (dry run — would post buyer invite)")
                    approached += 1
                    found = True
                    break

                comment = _buyer_comment(author, relevant)
                data2, errors2 = _graphql(
                    ADD_COMMENT_MUTATION,
                    {"discussionId": disc_id, "body": comment},
                    token,
                )

                if errors2:
                    print(f"     ⚠️  Comment failed: {errors2[0].get('message', errors2)}")
                else:
                    comment_url = (data2 or {}).get("addDiscussionComment", {}).get("comment", {}).get("url", "")
                    print(f"     ✅ Buyer invite posted: {comment_url}")
                    state["engaged_discussions"].append(disc_id)
                    state["engaged_authors"].append(author)
                    _save_state(state)
                    approached += 1
                    time.sleep(30)

                found = True
                break  # one discussion per search term

    if not dry_run:
        _save_state(state)
    print(f"\n{'Would approach' if dry_run else 'Approached'} {approached} potential buyers.")


# ── Post pre-written discussions ──────────────────────────────────────────────

DISCUSSION_DRAFTS = {
    "microsoft/autogen": {
        "category": "Show and tell",
        "title": "External capability routing via schema hash — AutoGen agents buying inference from BOTmarket",
        "body": """\
I built a compute exchange called BOTmarket where agents buy inference by JSON schema hash — no hardcoded provider, no API key per seller. The buyer posts a schema hash + budget, the exchange matches a seller who registered that schema, escrows CU, calls the seller, settles atomically.

Here's how an AutoGen agent can use it as a tool:

```python
from autogen import ConversableAgent
from botmarket_sdk import BotMarket
import json, hashlib

bm = BotMarket("https://botmarket.dev", api_key="YOUR_KEY")

SCHEMA = {
    "input":  {"type": "text", "task": "summarize"},
    "output": {"type": "text", "result": "summary"},
}
CAP_HASH = hashlib.sha256(json.dumps(SCHEMA, sort_keys=True).encode()).hexdigest()[:16]

def buy_summary(text: str) -> str:
    \"\"\"Buy a text summary from the BOTmarket exchange.\"\"\"
    result = bm.buy(CAP_HASH, input={"type": "text", "task": "summarize", "text": text}, max_price_cu=5.0)
    return result.get("output", {}).get("result", "")

assistant = ConversableAgent("assistant", llm_config={"model": "gpt-4o-mini"})
assistant.register_for_llm(name="buy_summary", description="Buy a summary from BOTmarket")(buy_summary)
```

The agent doesn't know it's calling qwen2.5:7b on someone's local machine. It just sees a tool that returns summaries. The exchange handles matching, escrow, SLA enforcement (bond slashing on failure), and settlement.

This is interesting for multi-agent workflows — each agent in a group chat can independently buy capabilities it lacks, without the orchestrator needing to know which provider serves what. Schema-hash addressing means the buyer's code never changes when sellers rotate.

**Setup:**
```bash
pip install botmarket-sdk
# Get 500 free CU:
curl -X POST https://botmarket.dev/v1/faucet -H "X-API-Key: YOUR_KEY"
```

Full onboarding (LLM-parseable): https://botmarket.dev/skill.md
Live stats: https://botmarket.dev/v1/stats

Happy to answer questions about the schema hash mechanism or the escrow/settlement flow.""",
    },
    "pydantic/pydantic": {
        "category": "Projects using Pydantic",
        "title": "BOTmarket — compute exchange using Pydantic models for schema-hash capability matching",
        "body": """\
Pydantic's schema-first design maps naturally to an exchange I've been building: BOTmarket addresses compute capabilities by the SHA-256 hash of their JSON input/output schema. A buyer says "I need this schema", the exchange finds a seller who registered it, escrows CU, calls them, settles.

Since Pydantic models serialize to JSON Schema deterministically, they're a natural fit for the addressing layer. Here's an example using pydantic-ai's `Tool`:

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
    \"\"\"Buy a text summary from the BOTmarket exchange.\"\"\"
    result = bm.buy(CAP_HASH, input={"type": "text", "task": "summarize", "text": input.text}, max_price_cu=5.0)
    return SummarizeOutput(summary=result["output"]["result"])

agent = Agent(
    "openai:gpt-4o-mini",
    tools=[Tool(buy_summary, takes_ctx=False)],
    system_prompt="You are an assistant. Use buy_summary for long texts.",
)
```

The schema hash on the buy side is computed from the same structure the seller registered. The exchange does exact-match routing — no fuzzy category system. This means Pydantic models on both sides of a trade can be round-tripped through the hash without ambiguity.

The whole exchange (FastAPI + PostgreSQL) uses Pydantic for request/response validation throughout. The SDK is on PyPI: `pip install botmarket-sdk`.

**To get started:**
```bash
pip install botmarket-sdk
curl -X POST https://botmarket.dev/v1/faucet -H "X-API-Key: YOUR_KEY"
```

Full spec (LLM-parseable): https://botmarket.dev/skill.md
Source: https://github.com/mariuszr1979/BOTmarket

Curious if anyone else has tried routing Pydantic-validated tool calls through an external exchange layer.""",
    },
    "run-llama/llama_index": {
        "category": "Show and tell",
        "title": "LlamaIndex agents buying external inference via BOTmarket — schema-hash capability exchange",
        "body": """\
I built a compute exchange called BOTmarket where AI agents buy and sell inference capabilities by JSON schema hash. Instead of hardcoding API keys to specific providers, agents post a capability hash + budget and the exchange matches them to the cheapest seller automatically.

Here's how a LlamaIndex agent can use it as a `FunctionTool`:

```python
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from botmarket_sdk import BotMarket
import json, hashlib

bm = BotMarket("https://botmarket.dev", api_key="YOUR_KEY")

SCHEMA = {
    "input":  {"type": "text", "task": "summarize"},
    "output": {"type": "text", "result": "summary"},
}
CAP_HASH = hashlib.sha256(json.dumps(SCHEMA, sort_keys=True).encode()).hexdigest()[:16]

def buy_summary(text: str) -> str:
    \"\"\"Buy a text summary from the BOTmarket exchange. Routes to cheapest available seller.\"\"\"
    result = bm.buy(CAP_HASH, input={"type": "text", "task": "summarize", "text": text}, max_price_cu=5.0)
    return result.get("output", {}).get("result", "")

tool = FunctionTool.from_defaults(fn=buy_summary)
agent = ReActAgent.from_tools([tool], llm=OpenAI(model="gpt-4o-mini"), verbose=True)
agent.chat("Summarize this article: [...]")
```

The agent doesn't know the summary comes from qwen2.5:7b on someone's local Ollama. It just sees a tool that returns summaries. The exchange handles:

- **Matching** — finds cheapest seller for the schema hash
- **Escrow** — locks CU before calling the seller
- **SLA enforcement** — sellers stake a bond (5% of price), slashed on failure
- **Settlement** — atomic release of CU to seller (minus 1.5% fee)

This is interesting for LlamaIndex's tool abstraction — any capability on the exchange becomes a `FunctionTool` without managing provider credentials. Schema-hash addressing means the agent's code never changes when sellers rotate.

**The seller side is also simple** — if you have Ollama running locally:

```bash
pip install botmarket-sdk
botmarket-sell   # auto-detects models, opens tunnel, registers on exchange
```

**Setup (buyer):**
```bash
pip install botmarket-sdk
curl -X POST https://botmarket.dev/v1/faucet -H "X-API-Key: YOUR_KEY"
```

Full onboarding (LLM-parseable): https://botmarket.dev/skill.md
Source: https://github.com/mariuszr1979/BOTmarket
Live stats: https://botmarket.dev/v1/stats

Happy to answer questions about the protocol or integration patterns.""",
    },
}


def cmd_post_discussions(dry_run=False):
    """Post pre-written introductory discussions to target repos."""
    token = _get_token()
    state = _load_state()

    print("═══ BOTmarket GitHub Discussion Posts ═══\n")

    posted = 0

    for repo, draft in DISCUSSION_DRAFTS.items():
        if repo in state.get("posted_repos", []):
            print(f"  · Already posted to {repo}")
            continue

        owner, name = repo.split("/")

        print(f"\n  📝 {repo}")
        print(f"     Title: {draft['title'][:65]}")
        print(f"     Category: {draft['category']}")

        if dry_run:
            print(f"     (dry run — would create discussion)")
            posted += 1
            continue

        # Get repo ID
        data, errors = _graphql(GET_REPO_ID, {"owner": owner, "name": name}, token)
        if errors or not data:
            print(f"     ⚠️  Could not get repo ID: {errors}")
            continue
        repo_id = data["repository"]["id"]

        # Get discussion category ID
        data2, errors2 = _graphql(
            GET_REPO_DISCUSSION_CATEGORIES,
            {"owner": owner, "name": name},
            token,
        )
        if errors2 or not data2:
            print(f"     ⚠️  Could not get categories: {errors2}")
            continue

        categories = data2["repository"]["discussionCategories"]["nodes"]
        target_category = draft["category"].lower()
        cat_id = None
        for cat in categories:
            if cat["name"].lower() == target_category or cat["slug"] == target_category:
                cat_id = cat["id"]
                break

        if not cat_id:
            # Fallback: use first category (usually "General")
            available = [c["name"] for c in categories]
            print(f"     ⚠️  Category '{draft['category']}' not found. Available: {available}")
            # Try "General" as fallback
            for cat in categories:
                if cat["name"].lower() == "general":
                    cat_id = cat["id"]
                    break
            if not cat_id and categories:
                cat_id = categories[0]["id"]
                print(f"     Using fallback category: {categories[0]['name']}")

        if not cat_id:
            print(f"     ⚠️  No discussion categories available. Discussions may be disabled.")
            continue

        data3, errors3 = _graphql(
            CREATE_DISCUSSION_MUTATION,
            {
                "repoId": repo_id,
                "categoryId": cat_id,
                "title": draft["title"],
                "body": draft["body"],
            },
            token,
        )

        if errors3:
            print(f"     ⚠️  Post failed: {errors3[0].get('message', errors3)}")
        else:
            disc = (data3 or {}).get("createDiscussion", {}).get("discussion", {})
            print(f"     ✅ Posted: {disc.get('url', '(no url)')}")
            state.setdefault("posted_repos", []).append(repo)
            _save_state(state)
            posted += 1
            time.sleep(60)  # courtesy pause between repos

    print(f"\n{'Would post to' if dry_run else 'Posted to'} {posted} repos.")


# ── Daemon mode ──────────────────────────────────────────────────────────────

_DAEMON_SCHEDULE = [
    (lambda: cmd_scout_sellers(False), 12 * 3600, "scout-sellers"),
    (lambda: cmd_scout_buyers(False),  12 * 3600, "scout-buyers"),
]

_log = logging.getLogger("github-scout-daemon")


def cmd_daemon():
    """Run scouts on a recurring schedule."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _log.info("GitHub scout daemon starting")

    last_run: dict[str, float] = {}

    while True:
        now = time.time()
        for func, interval, label in _DAEMON_SCHEDULE:
            if now - last_run.get(label, 0) >= interval:
                _log.info("Running %s", label)
                try:
                    func()
                except Exception:
                    _log.exception("Error in %s", label)
                last_run[label] = time.time()
                time.sleep(60)

        time.sleep(300)


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="BOTmarket GitHub Discussions scout agent"
    )
    sub = parser.add_subparsers(dest="cmd")

    s = sub.add_parser("scout-sellers", help="Find devs who could sell capabilities we lack")
    s.add_argument("--dry-run", action="store_true")

    b = sub.add_parser("scout-buyers", help="Find devs who might buy capabilities we offer")
    b.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("post-discussions", help="Post intro discussions to target repos")
    p.add_argument("--dry-run", action="store_true")

    sub.add_parser("daemon", help="Run scouts on a 12-hour schedule")

    args = parser.parse_args()

    if args.cmd == "scout-sellers":
        cmd_scout_sellers(dry_run=args.dry_run)
    elif args.cmd == "scout-buyers":
        cmd_scout_buyers(dry_run=args.dry_run)
    elif args.cmd == "post-discussions":
        cmd_post_discussions(dry_run=args.dry_run)
    elif args.cmd == "daemon":
        cmd_daemon()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
