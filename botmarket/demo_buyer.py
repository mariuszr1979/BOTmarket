#!/usr/bin/env python3
# demo_buyer.py — Demo: register a buyer, match to agents, execute real Ollama trades
"""
Usage:
  1. Start exchange:  bash launch.sh
  2. Run demo:        python demo_buyer.py

This registers a buyer agent, seeds it with CU, then runs trades against
the first-party sellers using real Ollama inference.
"""
import json
import urllib.request
from agents import AGENTS, _capability_hash, execute

EXCHANGE_URL = "http://localhost:8000"


def _api(method, path, body=None, api_key=None):
    url = f"{EXCHANGE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    print("═══ BOTmarket Demo Buyer ═══\n")

    # Register buyer
    buyer = _api("POST", "/v1/agents/register")
    print(f"Buyer registered: {buyer['agent_id'][:16]}…")

    # Seed buyer with CU (direct DB for demo — in production, this is USDC on-ramp)
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from db import get_connection
    conn = get_connection()
    conn.execute("UPDATE agents SET cu_balance = 500.0 WHERE pubkey = ?", (buyer["agent_id"],))
    conn.commit()
    conn.close()
    print("Buyer seeded: 500 CU\n")

    # Demo inputs for each agent
    demos = [
        ("Summarizer", "The quick brown fox jumped over the lazy dog. This sentence is a classic English pangram that contains every letter of the alphabet at least once. It has been used since the late 19th century for typing practice and font demonstrations."),
        ("Translator", "The weather is beautiful today. I would like to go for a walk in the park."),
        ("CodeLinter", "def foo(x):\n  y = x+1\n  return y\n  print('unreachable')\nimport os"),
        ("DataExtractor", "John Smith, age 34, lives at 123 Main St, Springfield IL 62704. Phone: 555-1234. Email: john@example.com"),
    ]

    for agent_name, input_text in demos:
        agent_def = next(a for a in AGENTS if a["name"] == agent_name)
        cap_hash = _capability_hash(agent_def["input_schema"], agent_def["output_schema"])

        print(f"─── {agent_name} ({agent_def['price_cu']} CU) ───")

        # Match
        match = _api("POST", "/v1/match", {"capability_hash": cap_hash}, buyer["api_key"])
        if match["status"] != "matched":
            print(f"  ✗ {match['status']}")
            continue
        trade_id = match["trade_id"]
        print(f"  Matched → trade {trade_id[:12]}…")

        # Execute via exchange (records the trade)
        exec_resp = _api("POST", f"/v1/trades/{trade_id}/execute",
                          {"input": input_text}, buyer["api_key"])
        print(f"  Exchange executed → {exec_resp['status']}")

        # Real Ollama inference (the actual work the agent does)
        print(f"  Running {agent_def['model']}…", end=" ", flush=True)
        output = execute(agent_name, input_text)
        print(f"done ({len(output)} chars)")
        print(f"  Output: {output[:120]}{'…' if len(output) > 120 else ''}")

        # Settle
        settle = _api("POST", f"/v1/trades/{trade_id}/settle",
                        api_key=buyer["api_key"])
        print(f"  Settled → {settle['status']}")
        print()

    # Final balance
    conn = get_connection()
    row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (buyer["agent_id"],)).fetchone()
    conn.close()
    print(f"Buyer final balance: {row['cu_balance']:.1f} CU")


if __name__ == "__main__":
    main()
