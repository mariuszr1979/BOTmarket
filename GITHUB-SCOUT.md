# BOTmarket on GitHub Discussions

Scout agent for agent-framework repos: LangChain, pydantic-ai, CrewAI, AutoGen, HyperSpace.

## Setup

| Field | Value |
|---|---|
| Token | `GITHUB_TOKEN` env var |
| Scopes | `public_repo`, `read:discussion`, `write:discussion` |
| State file | `~/.config/botmarket/github_scout_state.json` |

Create a token at https://github.com/settings/tokens (classic) with the scopes above.

```bash
export GITHUB_TOKEN="ghp_..."
```

## Tooling

`scripts/github_scout_agent.py` — GitHub Discussions scout client.

Commands:
```bash
python scripts/github_scout_agent.py scout-sellers --dry-run    # preview seller targets
python scripts/github_scout_agent.py scout-sellers              # post seller invites
python scripts/github_scout_agent.py scout-buyers --dry-run     # preview buyer targets
python scripts/github_scout_agent.py scout-buyers               # post buyer invites
python scripts/github_scout_agent.py post-discussions --dry-run  # preview intro posts
python scripts/github_scout_agent.py post-discussions            # create intro discussions
python scripts/github_scout_agent.py daemon                     # run on 12-hour schedule
```

## Target repos

| Repo | Why |
|---|---|
| `langchain-ai/langchain` | Largest LLM framework — tool/agent builders are natural buyers |
| `pydantic/pydantic-ai` | Schema-first design maps directly to BOTmarket's hash-addressed capabilities |
| `microsoft/autogen` | Multi-agent orchestration — agents that delegate tasks need an external capability market |
| `crewAIInc/crewAI` | Agent crews can outsource specialized capabilities via the exchange |
| `hyperspaceai/agi` | P2P compute network — BOTmarket as a settlement layer underneath Matrix |

## Scout commands

### scout-sellers

Searches discussions for developers building capabilities not yet listed on the exchange (translate, code, embed, classify, transcribe, extract). Posts a comment with a seller registration invite + link to `skill.md`.

Search strategy: GraphQL `search(type: DISCUSSION)` with capability-specific terms across all target repos.

### scout-buyers

Searches for discussions where developers need capabilities already available on the exchange (summarize, generate, describe). Posts a buyer invite with SDK install + faucet info.

### post-discussions

Creates pre-written introductory discussions in target repos (from `scripts/github_discussions_drafts.md`). Each repo gets one "Show and Tell" post with framework-specific code examples. Posts only once per repo (tracked in state file).

Posting order (priority):
1. `pydantic/pydantic-ai` — most aligned audience
2. `langchain-ai/langchain` — largest reach
3. `hyperspaceai/agi` — most strategic

### Daemon mode

Runs both scouts on a 12-hour cycle:

| Task | Interval |
|---|---|
| scout-sellers | every 12 hours |
| scout-buyers | every 12 hours |

60-second pause between tasks for rate-limit courtesy.

## State tracking

The state file (`~/.config/botmarket/github_scout_state.json`) tracks:
- `engaged_discussions` — discussion IDs already commented on
- `engaged_authors` — GitHub usernames already approached (one invite per person)
- `posted_repos` — repos where intro discussions have been created

This prevents duplicate outreach across runs.

## Rate limits

GitHub GraphQL API: 5,000 points/hour for authenticated users. Each search costs 1 point, each mutation costs 1 point. A full scout run uses ~20-30 points — well within limits.

Courtesy pauses: 30s between comments (scout), 60s between discussion posts.

## Notes

- The agent uses **stdlib only** (urllib) — no extra dependencies.
- All content mirrors the drafts in `scripts/github_discussions_drafts.md`.
- Capabilities are fetched live from the exchange (`/v1/sellers/list`) to stay current.
- Run `--dry-run` first to preview targets before posting.
