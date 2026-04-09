#!/usr/bin/env bash
# launch_outreach.sh — Deploy all outreach channels
#
# Prerequisites:
#   1. Set GITHUB_TOKEN env var  (ghp_... with public_repo + write:discussion)
#   2. Ollama running locally     (for Moltbook LLM replies)
#   3. Moltbook credentials        (~/.config/moltbook/ or MOLTBOOK_API_KEY)
#
# Usage:
#   export GITHUB_TOKEN="ghp_..."
#   bash scripts/launch_outreach.sh
#
set -euo pipefail
cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     BOTmarket Outreach Launch Checklist      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Preflight ─────────────────────────────────────────────

echo "① Preflight checks …"
READY=true

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    ok "GITHUB_TOKEN set (${GITHUB_TOKEN:0:4}...)"
else
    fail "GITHUB_TOKEN not set — GitHub scout will NOT run"
    warn "Create one: https://github.com/settings/tokens (public_repo + write:discussion)"
    READY=false
fi

if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    MODEL_COUNT=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo 0)
    ok "Ollama running ($MODEL_COUNT models)"
else
    warn "Ollama not running — Moltbook LLM replies will queue offline"
fi

if curl -sf https://botmarket.dev/v1/health >/dev/null 2>&1; then
    ok "botmarket.dev reachable"
else
    fail "botmarket.dev unreachable — outreach links will 404"
    READY=false
fi

if [[ -f ~/.config/moltbook/session.json ]] || [[ -n "${MOLTBOOK_API_KEY:-}" ]]; then
    ok "Moltbook credentials found"
else
    warn "No Moltbook credentials — Moltbook agent will NOT post"
fi

echo ""

# ── GitHub Scout (automated) ─────────────────────────────

echo "② GitHub Discussions outreach …"
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    echo "  Running scout-sellers --dry-run first …"
    cd scripts
    if python3 github_scout_agent.py scout-sellers --dry-run 2>&1 | head -20; then
        echo ""
        read -p "  Post seller invitations for real? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 github_scout_agent.py scout-sellers 2>&1 | tail -10
            ok "Seller invitations posted"
        else
            warn "Skipped seller invitations"
        fi

        echo ""
        echo "  Running scout-buyers --dry-run …"
        python3 github_scout_agent.py scout-buyers --dry-run 2>&1 | head -20
        echo ""
        read -p "  Post buyer invitations for real? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 github_scout_agent.py scout-buyers 2>&1 | tail -10
            ok "Buyer invitations posted"
        else
            warn "Skipped buyer invitations"
        fi

        echo ""
        echo "  Running post-discussions --dry-run …"
        python3 github_scout_agent.py post-discussions --dry-run 2>&1 | head -20
        echo ""
        read -p "  Post intro discussions for real? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 github_scout_agent.py post-discussions 2>&1 | tail -10
            ok "Intro discussions posted"
        else
            warn "Skipped intro discussions"
        fi
    fi
    cd ..
else
    warn "Skipping GitHub — no token"
fi

echo ""

# ── Reddit (manual — print drafts) ───────────────────────

echo "③ Reddit posts (MANUAL — copy-paste) …"
echo ""
echo "  Posts ready to copy-paste from:"
echo "    • scripts/reddit_locallama_draft.md    → r/LocalLLaMA"
echo "    • scripts/reddit_4_subs_drafts.md      → r/MachineLearning, r/selfhosted, r/artificial, r/SideProject"
echo "    • scripts/botmarket_sell_announcement.md → r/LocalLLaMA, r/ollama"
echo ""
echo "  Recommended schedule:"
echo "    Day 1 (today):  r/LocalLLaMA  (tuesday 18:00 CET = 9am PDT is optimal)"
echo "    Day 2:          r/selfhosted, r/MachineLearning"
echo "    Day 3:          r/artificial, r/SideProject"
echo ""

# ── A2A Directories (manual) ─────────────────────────────

echo "④ A2A Directory submissions (MANUAL — ~20 min total) …"
echo ""
echo "  Full instructions: scripts/a2a-directory-submissions.md"
echo ""
echo "  1. https://a2acatalog.com/submit           (~5 min)"
echo "  2. https://github.com/BenjaminScottAwk/awesome-a2a  (PR, ~10 min)"
echo "  3. https://aiagentsdirectory.com/submit-agent       (~5 min)"
echo ""

# ── Moltbook announcement ────────────────────────────────

echo "⑤ Moltbook SDK + PyPI announcement …"
if [[ -f ~/.config/moltbook/session.json ]] || [[ -n "${MOLTBOOK_API_KEY:-}" ]]; then
    echo "  Posting SDK install announcement (now that PyPI is live) …"
    cd scripts
    python3 moltbook_agent.py post \
        "botmarket-sdk is on PyPI — pip install botmarket-sdk. One command to sell your Ollama models: botmarket-sell. Auto-detects models, opens tunnel, registers on exchange. Zero config." \
        --dry-run 2>&1 | head -10 || warn "Moltbook post dry-run failed"
    echo ""
    read -p "  Post for real? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 moltbook_agent.py post \
            "botmarket-sdk is on PyPI — pip install botmarket-sdk. One command to sell your Ollama models: botmarket-sell. Auto-detects models, opens tunnel, registers on exchange. Zero config." \
            2>&1 | tail -5
        ok "Moltbook announcement posted"
    fi
    cd ..
else
    warn "Skipping Moltbook — no credentials"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Summary                                     ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  GitHub:    Automated (needs GITHUB_TOKEN)   ║"
echo "║  Reddit:    Manual copy-paste from drafts    ║"
echo "║  A2A dirs:  Manual web forms (~20 min)       ║"
echo "║  Moltbook:  Automated (needs credentials)    ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
