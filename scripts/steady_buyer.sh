#!/usr/bin/env bash
# steady_buyer.sh — Generate a steady stream of trades on the live exchange.
# Runs a buy every 10 minutes to keep the dashboard alive.
# Uses the Moltbook buyer agent's API key.
set -e
cd "$(dirname "$0")"
source ../botmarket/.venv/bin/activate

export BOTMARKET_API_KEY="72ab5556e6de659721410e7cfebf1a32375555075b0c0a40797c56817f99f4a3"
export BOTMARKET_URL="https://botmarket.dev"

python3 - <<'PYEOF'
import json, os, random, time, urllib.request, urllib.error

API_KEY = os.environ["BOTMARKET_API_KEY"]
BASE    = os.environ["BOTMARKET_URL"].rstrip("/")

# Capability hashes on production
CAPS = {
    "summarize": "c4f9d9ee8168ee3d521e0bf0519c8eaf6635cfe41c178e0b1fb49591a3399c60",
    "generate":  "e560d9328c6e3c2029a01e80c3e80c0e6a3b4d7f8e1a2d5c4b3a6f9e8d7c0b1a",
}

PROMPTS = {
    "summarize": [
        "Summarize: AI agents are autonomous programs that can perceive, decide, and act on behalf of users or other systems.",
        "Summarize: Compute exchanges allow agents to trade inference capabilities using schema-hash addressing and atomic settlement.",
        "Summarize: The BOTmarket protocol matches buyers and sellers by capability hash, handles escrow, and settles with a 1.5% fee.",
        "Summarize: Local LLMs running on consumer hardware can be monetized by registering as sellers on compute exchanges.",
        "Summarize: Zero-config tools like botmarket-sell detect Ollama models, open a tunnel, and register capabilities automatically.",
    ],
}

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=data, method="POST",
        headers={"Content-Type": "application/json", "X-Api-Key": API_KEY},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())

def do_trade():
    cap_name = "summarize"
    cap_hash = CAPS[cap_name]
    prompt = random.choice(PROMPTS[cap_name])

    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] Buying {cap_name} …", flush=True)

    try:
        match = post("/v1/match", {"capability_hash": cap_hash, "max_price_cu": 10})
    except urllib.error.HTTPError as e:
        print(f"  match failed: {e.code} {e.read().decode()[:100]}", flush=True)
        return

    if match.get("status") != "matched":
        print(f"  no match: {match.get('status')}", flush=True)
        return

    trade_id = match["trade_id"]
    try:
        exc = post(f"/v1/trades/{trade_id}/execute", {"input": prompt})
        output = exc.get("output", "")[:120]
        latency = exc.get("latency_us", 0) / 1000
        print(f"  executed: {latency:.0f}ms — {output}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  execute failed: {e.code}", flush=True)
        return

    try:
        post(f"/v1/trades/{trade_id}/settle", {})
        print(f"  ✓ settled (trade {trade_id[:8]}…)", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  settle failed: {e.code}", flush=True)

INTERVAL = 600  # 10 minutes

print(f"Steady buyer started — 1 trade every {INTERVAL//60} min")
print(f"Exchange: {BASE}")
print(f"Agent: {API_KEY[:8]}…\n", flush=True)

while True:
    try:
        do_trade()
    except Exception as e:
        print(f"  error: {e}", flush=True)
    time.sleep(INTERVAL)
PYEOF
