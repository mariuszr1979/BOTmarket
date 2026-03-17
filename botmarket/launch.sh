#!/usr/bin/env bash
# launch.sh — Start BOTmarket exchange + register first-party agents
set -e
cd "$(dirname "$0")"

echo "═══════════════════════════════════════════"
echo " BOTmarket — Local Launch"
echo "═══════════════════════════════════════════"

# Activate venv
source .venv/bin/activate

# Start JSON sidecar (port 8000)
echo "[1/3] Starting JSON API on :8000…"
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level warning &
PID_JSON=$!

# Start TCP server (port 9000)
echo "[2/3] Starting TCP server on :9000…"
python tcp_server.py &
PID_TCP=$!

# Wait for API to come up
sleep 1
for i in $(seq 1 10); do
    if curl -sf http://localhost:8000/v1/health > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# Health check
echo ""
curl -s http://localhost:8000/v1/health | python3 -m json.tool
echo ""

# Register first-party agents
echo "[3/3] Registering first-party agents…"
python agents.py

echo ""
echo "═══════════════════════════════════════════"
echo " Exchange running — PIDs: JSON=$PID_JSON TCP=$PID_TCP"
echo " JSON: http://localhost:8000"
echo " TCP:  tcp://localhost:9000"
echo " Stop: kill $PID_JSON $PID_TCP"
echo "═══════════════════════════════════════════"

# Keep running
wait
