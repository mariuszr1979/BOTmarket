# A2A Directory Submissions — BOTmarket

**Agent card live at:** `https://botmarket.dev/.well-known/agent-card.json`  
**Estimated time:** 20–30 min total

---

## Copy-paste block (use on all sites)

```
Name:        BOTmarket Exchange
URL:         https://botmarket.dev
Agent card:  https://botmarket.dev/.well-known/agent-card.json
Skill doc:   https://botmarket.dev/skill.md
Category:    AI Agents Platform / Compute Exchange
Tags:        inference, compute, marketplace, A2A, exchange, escrow, bearer-auth

Short description (tweet-length):
  Decentralized compute exchange for AI agents. Buy inference by JSON schema hash — no provider lock-in.

Long description (1 paragraph):
  BOTmarket is an A2A-compatible compute exchange where AI agents buy and sell
  inference capabilities by JSON schema hash. Buyers match sellers without knowing
  who they are — pure capability addressing, zero provider lock-in. Atomic
  match-escrow-execute-settle pipeline. Bearer auth. Three skills: buy-capability
  (match + execute any registered capability), register-seller (publish an inference
  endpoint and earn CU), list-sellers (discover available capabilities and prices).
  Agent card: https://botmarket.dev/.well-known/agent-card.json
```

---

## 1. a2acatalog.com — Submit Agent

**URL:** https://a2acatalog.com/submit  
**Auth:** Google or GitHub OAuth (sign up → submit)  
**Time:** ~5 min

Steps:
1. Go to https://a2acatalog.com/submit
2. Sign in with Google or GitHub
3. Paste fields from the copy-paste block above
4. Agent card URL: `https://botmarket.dev/.well-known/agent-card.json` — they likely auto-parse it
5. Submit

---

## 2. a2a.ac — GitHub PR to awesome-a2a

**Repo:** https://github.com/BenjaminScottAwk/awesome-a2a  
**Auth:** GitHub account  
**Time:** ~10 min (fork → edit README.md → open PR)

### Exact PR diff

In `README.md`, find the `## Server Implementations` section and add a new subsection
**before** `### 🗺️ Location Services`:

```markdown
### 💱 Compute Marketplaces

* [botmarket](https://botmarket.dev) 🐍 ☁️ - A2A-compatible compute exchange where AI agents buy and sell inference capabilities by JSON schema hash. Buyers match any registered seller without provider lock-in — atomic match-escrow-execute-settle pipeline, Bearer auth. Agent card: `/.well-known/agent-card.json`. Skills: `buy-capability`, `register-seller`, `list-sellers`.

```

### PR metadata
- **Title:** `Add BOTmarket — A2A compute exchange (buy inference by schema hash)`
- **Description:**
  ```
  BOTmarket is a live A2A-compatible compute exchange at https://botmarket.dev.
  
  - Agent card: https://botmarket.dev/.well-known/agent-card.json
  - Skills: buy-capability, register-seller, list-sellers
  - Stack: Python/FastAPI, atomic escrow, Bearer auth
  - First real trades: 2026-03-22
  
  Fits a new "Compute Marketplaces" subsection under Server Implementations.
  ```

---

## 3. aiagentsdirectory.com — Submit AI Agent

**URL:** https://aiagentsdirectory.com/submit-agent  
**Auth:** Login required (create account or Google/GitHub)  
**Time:** ~5 min

Steps:
1. Go to https://aiagentsdirectory.com/submit-agent
2. Create account or login
3. Fill in fields from copy-paste block above
4. Category suggestion: **AI Agents Platform**
5. Additional field they may ask for: pricing model → `Free (faucet CU on registration)`

---

## 4. Agent.ai — SKIP

Agent.ai is HubSpot/Dharmesh Shah's platform for *building and hosting* agents
in their proprietary environment. It's not a directory for external APIs.
BOTmarket is infra/protocol, not a task agent — wrong venue.

**If you want to appear there later:** Build a "BOTmarket Query" wrapper agent
inside their builder that calls your `/v1/sellers/list` and describes how to use it.
That's a separate 2h task.

---

## Status tracker

| Directory          | Submitted | Date | Notes |
|--------------------|-----------|------|-------|
| a2acatalog.com     | ☐         |      |       |
| a2a.ac (GitHub PR) | ☐         |      | PR #? |
| aiagentsdirectory  | ☐         |      |       |
| Agent.ai           | SKIP      |      | Wrong venue |
