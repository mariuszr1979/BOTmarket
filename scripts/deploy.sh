#!/usr/bin/env bash
# deploy.sh — First-deploy script for a fresh Ubuntu 22.04 VPS
#
# Run as root (or with sudo) on the target server:
#   curl -fsSL https://raw.githubusercontent.com/your-org/botmarket/main/scripts/deploy.sh | bash
#   — OR —
#   git clone ... && cd BOTmarket && bash scripts/deploy.sh
#
# What it does:
#   1. Installs Docker + Docker Compose plugin
#   2. Clones / updates the repo (if not already present)
#   3. Creates .env from .env.example if missing (operator must fill secrets)
#   4. Starts the stack with docker compose up -d
#   5. Prints health status

set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/botmarket}"
COMPOSE_DIR="$REPO_DIR/botmarket"
REPO_URL="${REPO_URL:-}"   # set via env if cloning from Git

# ── 1. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "▶ Installing Docker…"
    apt-get update -q
    apt-get install -y -q ca-certificates curl gnupg lsb-release
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
else
    echo "✓ Docker already installed: $(docker --version)"
fi

# Ensure compose plugin is available
if ! docker compose version &>/dev/null 2>&1; then
    echo "▶ Installing Docker Compose plugin…"
    apt-get install -y -q docker-compose-plugin
fi

# ── 2. Repo ───────────────────────────────────────────────────────────────────
if [[ -d "$REPO_DIR/.git" ]]; then
    echo "▶ Pulling latest code…"
    git -C "$REPO_DIR" pull --ff-only
elif [[ -n "$REPO_URL" ]]; then
    echo "▶ Cloning repo to $REPO_DIR…"
    git clone "$REPO_URL" "$REPO_DIR"
elif [[ -d "$REPO_DIR" ]]; then
    echo "✓ Using existing directory $REPO_DIR"
else
    echo "ERROR: REPO_DIR=$REPO_DIR does not exist and REPO_URL is not set."
    echo "       Run this script from inside the cloned repo directory, or set REPO_URL."
    exit 1
fi

# ── 3. Environment ────────────────────────────────────────────────────────────
ENV_FILE="$COMPOSE_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "▶ Creating .env from .env.example — FILL IN SECRETS BEFORE CONTINUING"
    cp "$COMPOSE_DIR/.env.example" "$ENV_FILE"
    # Generate a random postgres password automatically
    PG_PASS=$(openssl rand -hex 24)
    sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$PG_PASS/" "$ENV_FILE"
    echo ""
    echo "  .env created at $ENV_FILE"
    echo "  POSTGRES_PASSWORD has been auto-generated."
    echo "  Review and adjust other settings, then re-run this script."
    echo ""
else
    echo "✓ .env already exists — skipping"
fi

# Abort if placeholder password is still set
if grep -q "^POSTGRES_PASSWORD=changeme" "$ENV_FILE"; then
    echo "ERROR: .env still has placeholder POSTGRES_PASSWORD=changeme"
    echo "       Edit $ENV_FILE and set a real password, then re-run."
    exit 1
fi

# ── 4. Build + start ─────────────────────────────────────────────────────────
echo "▶ Copying live.html into build context…"
cp "$REPO_DIR/slides/live.html" "$COMPOSE_DIR/live.html"

echo "▶ Building and starting stack…"
cd "$COMPOSE_DIR"
docker compose pull postgres 2>/dev/null || true
docker compose up -d --build

# ── 5. Health check ───────────────────────────────────────────────────────────
echo "▶ Waiting for exchange to become healthy…"
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/v1/health > /dev/null 2>&1; then
        echo ""
        echo "═══════════════════════════════════════════"
        echo " BOTmarket — LIVE"
        echo "═══════════════════════════════════════════"
        curl -s http://localhost:8000/v1/health
        echo ""
        echo " JSON API : http://$(hostname -I | awk '{print $1}'):8000"
        echo " TCP      : tcp://$(hostname -I | awk '{print $1}'):9000"
        echo " Health   : http://localhost:8000/v1/health"
        echo " Seed CU  : cd $REPO_DIR && python scripts/seed_cu.py <pubkey> [amount]"
        echo "═══════════════════════════════════════════"
        exit 0
    fi
    sleep 2
done

echo "ERROR: exchange did not become healthy within 60s"
echo "       Check logs: docker compose -f $COMPOSE_DIR/docker-compose.yml logs exchange"
exit 1
