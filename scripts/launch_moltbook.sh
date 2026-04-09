#!/usr/bin/env bash
# launch_moltbook.sh — Start Moltbook agent daemon with BOTmarket buyer integration
set -e
cd "$(dirname "$0")"

source ../botmarket/.venv/bin/activate

export BOTMARKET_URL="https://botmarket.dev"
export BOTMARKET_API_KEY="72ab5556e6de659721410e7cfebf1a32375555075b0c0a40797c56817f99f4a3"

echo "Starting Moltbook daemon…"
echo "  BOTMARKET_URL=$BOTMARKET_URL"
echo "  BOTMARKET_API_KEY=${BOTMARKET_API_KEY:0:8}…"

exec python moltbook_agent.py daemon
