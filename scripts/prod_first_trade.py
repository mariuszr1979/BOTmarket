#!/usr/bin/env python3
"""
prod_first_trade.py — Execute the first real trade on https://botmarket.dev

Steps:
  1. Operator (10M CU) registers as seller (schema + listing)
  2. Register a fresh legacy buyer
  3. SSH to VPS to seed buyer with 500 CU
  4. Match → Execute → Settle

Usage:
  cd /home/mariusz-raczko/Projects/BOTmarket
  python scripts/prod_first_trade.py
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Resolve botmarket package from scripts/../botmarket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "botmarket"))
from identity import sign_request  # noqa: E402

# ── Config ────────────────────────────────────────────────────────────────────

EXCHANGE_URL = os.environ.get("EXCHANGE_URL", "https://botmarket.dev")
OPERATOR_PRIV = os.environ.get(
    "OPERATOR_PRIV",
    "e06549376ed4e3657ec6e41698808aa5ae673b5c271f5ec9104164d8ec67bce4",
)
OPERATOR_PUB = os.environ.get(
    "OPERATOR_PUB",
    "2190b22f64e86690903418c95ca3f6f544061c2797eddf62676273d171e6545a",
)

VPS_HOST = "157.180.41.134"
VPS_USER = "root"
SSH_KEY = os.path.expanduser("~/.ssh/id_ed25519")

PRICE_CU = 20.0
CAPACITY = 10
BUYER_SEED_CU = 500.0

INPUT_SCHEMA = {"type": "string", "task": "summarize"}
OUTPUT_SCHEMA = {"type": "string", "result": "summary"}

# ── Helpers ───────────────────────────────────────────────────────────────────


def _capability_hash(input_schema, output_schema):
    ci = json.dumps(input_schema, sort_keys=True, separators=(",", ":"))
    co = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((ci + "||" + co).encode()).hexdigest()


def api(method, path, body=None, *, api_key=None, pub=None, priv=None):
    """Call the exchange JSON API. Returns (http_status, response_dict)."""
    url = f"{EXCHANGE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if pub and priv:
        sig, ts = sign_request(body if body is not None else b"", priv)
        headers["x-public-key"] = pub
        headers["x-signature"] = sig
        headers["x-timestamp"] = str(ts)
    elif api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            body_err = json.loads(e.read())
        except Exception:
            body_err = {"detail": str(e)}
        return e.code, body_err


def ssh(cmd):
    """Run a command on the VPS, return stdout as a string."""
    result = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
         f"{VPS_USER}@{VPS_HOST}", cmd],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SSH failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print("═══ BOTmarket — First Production Trade ═══\n")

    # ── Step 1: Operator registers schema ────────────────────────────────────
    cap_hash = _capability_hash(INPUT_SCHEMA, OUTPUT_SCHEMA)
    print(f"[1/5] Registering capability schema…")

    code, resp = api(
        "POST", "/v1/schemas/register",
        {"input_schema": INPUT_SCHEMA, "output_schema": OUTPUT_SCHEMA},
        pub=OPERATOR_PUB, priv=OPERATOR_PRIV,
    )
    if code in (200, 201):
        print(f"      Schema OK  ({resp['capability_hash'][:20]}…)")
    else:
        print(f"      Schema already/error ({code}): {resp.get('detail', resp)}")

    # ── Step 2: Operator registers as seller ─────────────────────────────────
    print(f"[2/5] Registering operator as seller @ {PRICE_CU} CU/trade…")

    code, resp = api(
        "POST", "/v1/sellers/register",
        {"capability_hash": cap_hash, "price_cu": PRICE_CU, "capacity": CAPACITY},
        pub=OPERATOR_PUB, priv=OPERATOR_PRIV,
    )
    if code in (200, 201):
        print(f"      Seller registered  (cap {cap_hash[:20]}…, capacity={CAPACITY})")
    elif code == 409:
        print(f"      Seller already registered — OK, continuing")
    else:
        print(f"      ERROR ({code}): {resp}")
        sys.exit(1)

    # ── Step 3: Register fresh buyer (legacy) ─────────────────────────────────
    print(f"[3/5] Registering fresh buyer…")

    code, buyer = api("POST", "/v1/agents/register")
    if code not in (200, 201):
        print(f"      ERROR ({code}): {buyer}")
        sys.exit(1)

    buyer_id = buyer["agent_id"]
    buyer_key = buyer["api_key"]
    print(f"      Buyer ID:   {buyer_id}")
    print(f"      API key:    {buyer_key[:16]}…")

    # ── Step 4: Seed buyer via SSH ────────────────────────────────────────────
    print(f"[4/5] Seeding buyer with {BUYER_SEED_CU:.0f} CU via SSH…")

    sql = (
        f"UPDATE agents SET cu_balance = {BUYER_SEED_CU} "
        f"WHERE pubkey = '{buyer_id}';"
    )
    seed_cmd = f"docker exec botmarket-postgres-1 psql -U botmarket -c \"{sql}\""

    out = ssh(seed_cmd)
    if "UPDATE 1" in out:
        print(f"      Seeded OK  ({BUYER_SEED_CU:.0f} CU → {buyer_id[:16]}…)")
    else:
        print(f"      Unexpected output: {out!r}")
        print("      Proceeding anyway — if balance is 0, match will return insufficient_cu")

    # ── Step 5: Match → Execute → Settle ─────────────────────────────────────
    print(f"\n[5/5] Running trade…")

    # Match
    code, match = api(
        "POST", "/v1/match",
        {"capability_hash": cap_hash},
        api_key=buyer_key,
    )
    status = match.get("status")
    if status != "matched":
        print(f"      ✗ Match failed: {match}")
        sys.exit(1)

    trade_id = match["trade_id"]
    print(f"      Match  → trade {trade_id[:12]}…  seller {match['seller_pubkey'][:12]}…  price {match['price_cu']} CU")

    # Execute
    input_text = (
        "BOTmarket is an open exchange where AI agents buy and sell compute units. "
        "This is the first real trade on the production system."
    )
    code, exec_resp = api(
        "POST", f"/v1/trades/{trade_id}/execute",
        {"input": input_text},
        api_key=buyer_key,
    )
    exec_status = exec_resp.get("status")
    latency_ms = exec_resp.get("latency_us", 0) // 1000
    print(f"      Execute → {exec_status}  (latency: {latency_ms} ms)")
    if exec_status not in ("executed", "completed"):
        print(f"      ERROR: {exec_resp}")
        sys.exit(1)

    # Settle
    code, settle = api(
        "POST", f"/v1/trades/{trade_id}/settle",
        api_key=buyer_key,
    )
    settle_status = settle.get("status")
    seller_receives = settle.get("seller_receives", "?")
    fee = settle.get("fee_cu", "?")
    print(f"      Settle → {settle_status}  seller_receives={seller_receives}  fee={fee}")

    if settle_status == "completed":
        print(f"""
╔═══════════���═══════════════════════════════╗
║  ✅  FIRST PRODUCTION TRADE COMPLETE!     ║
╚═══════════════════════════════════════════╝

  Exchange : {EXCHANGE_URL}
  Trade ID : {trade_id}
  Buyer    : {buyer_id[:20]}…
  Seller   : {OPERATOR_PUB[:20]}…
  Price    : {PRICE_CU} CU
  Settled  : {settle_status}
""")
    else:
        print(f"\n  Trade outcome: {settle_status} — details: {settle}")


if __name__ == "__main__":
    main()
