#!/usr/bin/env python3
"""ollama_seller.py — BOTmarket seller that routes executions to local Ollama models.

Registers 3 capabilities on startup:
  A: text generate  → llama3:latest      (5 CU)
  B: text summarize → qwen2.5:7b         (3 CU)
  C: image describe → llava:7b           (8 CU)

Usage:
    python ollama_seller.py [--tunnel]

    --tunnel   Auto-start a Cloudflare Tunnel and register with the tunnel URL.
               Requires cloudflared to be installed (or will try to install it).
"""
import argparse
import json
import logging
import os
import sys
import time
import urllib.request
import urllib.error

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, JSONResponse

# ── Add project root to path so ollama_client is importable ──────────────
sys.path.insert(0, os.path.dirname(__file__))
import ollama_client

# ── Configuration ─────────────────────────────────────────────────────────

EXCHANGE_URL  = os.environ.get("BOTMARKET_URL", "https://botmarket.dev")
API_KEY       = os.environ.get("BOTMARKET_API_KEY", "")
SELLER_PORT   = int(os.environ.get("SELLER_PORT", "8001"))
PUBLIC_URL    = os.environ.get("SELLER_PUBLIC_URL", "")   # overridden by --tunnel
BOND_SEED_KEY = os.environ.get("BOTMARKET_BOND_SEED_KEY", "")  # operator key to seed bond

# Path for persisting the agent API key across restarts
_KEY_FILE = os.path.join(os.path.dirname(__file__), ".seller_key")

# Capability definitions — (input_schema, output_schema, model, price_cu, capacity)
CAPABILITIES = [
    (
        {"type": "text", "task": "generate"},
        {"type": "text", "result": "generated_text"},
        "llama3:latest",
        5.0,
        5,
        "generate",
    ),
    (
        {"type": "text", "task": "summarize"},
        {"type": "text", "result": "summary"},
        "qwen2.5:7b",
        3.0,
        5,
        "summarize",
    ),
    (
        {"type": "image_base64", "task": "describe"},
        {"type": "text", "result": "description"},
        "llava:7b",
        8.0,
        3,
        "describe",
    ),
]

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
log = logging.getLogger("ollama_seller")

# ── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(title="BOTmarket Ollama Seller", version="0.1.0")

# Maps capability_hash → (model, task)
_cap_registry: dict[str, tuple[str, str]] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.head("/execute")
async def execute_head():
    """HEAD handler so the exchange's callback_url health check passes."""
    return Response(status_code=200)


@app.post("/execute")
async def execute(request: Request):
    """Receive an execute callback from the exchange, route to Ollama, return output."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON")

    input_data   = body.get("input", "")
    cap_hash     = body.get("capability_hash", "")
    trade_id     = body.get("trade_id", "")

    if cap_hash not in _cap_registry:
        # Accept any registered capability hash (and fall through to model dispatch)
        log.warning("unknown capability_hash %s — defaulting to summarize", cap_hash)

    model, task = _cap_registry.get(cap_hash, ("qwen2.5:7b", "summarize"))

    log.info("execute trade=%s cap=%s model=%s task=%s", trade_id, cap_hash[:8], model, task)

    try:
        if task == "describe":
            # Input is expected to be base64-encoded image bytes
            import base64
            try:
                image_bytes = base64.b64decode(input_data)
            except Exception:
                raise HTTPException(status_code=400, detail="input must be base64-encoded image for describe task")
            output = ollama_client.generate_with_image(
                model,
                "Describe this image in detail.",
                image_bytes,
            )
        elif task == "summarize":
            prompt = f"Summarize the following text concisely:\n\n{input_data}"
            output = ollama_client.generate(model, prompt)
        else:  # generate
            output = ollama_client.generate(model, input_data)
    except Exception as exc:
        log.error("ollama error: %s", exc)
        raise HTTPException(status_code=502, detail=f"ollama error: {exc}")

    log.info("done trade=%s output_len=%d", trade_id, len(output))
    return {"output": output}


# ── Exchange registration ─────────────────────────────────────────────────

def _exchange_post(path: str, body: dict, api_key: str) -> dict:
    url  = EXCHANGE_URL.rstrip("/") + path
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "X-Api-Key": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def _capability_hash(input_schema: dict, output_schema: dict) -> str:
    import hashlib
    canonical_in  = json.dumps(input_schema,  sort_keys=True, separators=(",", ":"))
    canonical_out = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((canonical_in + "||" + canonical_out).encode()).hexdigest()


def ensure_balance(api_key: str, needed_cu: float) -> None:
    """Check CU balance; try faucet if insufficient."""
    url = EXCHANGE_URL.rstrip("/") + "/v1/agents/me"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            balance = json.loads(resp.read()).get("cu_balance", 0.0)
    except Exception:
        return  # can't check, proceed anyway

    if balance < needed_cu:
        log.info("balance %.2f CU < needed %.2f — calling faucet", balance, needed_cu)
        try:
            result = _exchange_post("/v1/faucet", {}, api_key)
            log.info("faucet: credited %.2f CU", result.get("credited", 0))
        except Exception as exc:
            log.warning("faucet failed: %s — continue anyway", exc)


def register_capabilities(public_url: str, api_key: str) -> None:
    """Register all 3 capabilities on the exchange."""
    callback_url = public_url.rstrip("/") + "/execute"

    total_bond = sum(c[3] for c in CAPABILITIES)  # sum of price_cu for all caps
    ensure_balance(api_key, total_bond)

    for input_schema, output_schema, model, price_cu, capacity, task in CAPABILITIES:
        cap_hash = _capability_hash(input_schema, output_schema)

        # Register schema
        try:
            schema_resp = _exchange_post("/v1/schemas/register", {
                "input_schema": input_schema,
                "output_schema": output_schema,
            }, api_key)
            assert schema_resp["capability_hash"] == cap_hash
        except Exception as exc:
            log.error("schema register failed for %s: %s", task, exc)
            sys.exit(1)

        # Register seller
        try:
            sel_resp = _exchange_post("/v1/sellers/register", {
                "capability_hash": cap_hash,
                "price_cu": price_cu,
                "capacity": capacity,
                "callback_url": callback_url,
            }, api_key)
            log.info("registered capability %s (%s) hash=%s price=%.1f CU",
                     task, model, cap_hash[:12], price_cu)
        except Exception as exc:
            log.error("seller register failed for %s: %s", task, exc)
            sys.exit(1)

        _cap_registry[cap_hash] = (model, task)

    log.info("all %d capabilities registered. callback_url=%s", len(CAPABILITIES), callback_url)


# ── Entry point ───────────────────────────────────────────────────────────

def _get_tunnel_url(port: int) -> str:
    """Try to get a Cloudflare Tunnel URL for localhost:port."""
    try:
        from tunnel_helper import start_tunnel
        return start_tunnel(port)
    except ImportError:
        pass

    # Fallback: try running cloudflared directly
    import subprocess, threading, queue

    q: queue.Queue = queue.Queue()

    def _run():
        try:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                if "trycloudflare.com" in line or ".cloudflare-tunnel.com" in line:
                    # extract the https URL
                    import re
                    m = re.search(r"https://[^\s]+", line)
                    if m:
                        q.put(m.group(0))
                        return
        except FileNotFoundError:
            q.put(None)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    url = q.get(timeout=30)
    if url is None:
        log.error("cloudflared not found. Install it: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/")
        sys.exit(1)
    return url


def _load_or_register_key() -> str:
    """Return API key: env var > .seller_key file > register fresh and save."""
    if API_KEY:
        return API_KEY
    if os.path.isfile(_KEY_FILE):
        key = open(_KEY_FILE).read().strip()
        if key:
            log.info("loaded API key from %s", _KEY_FILE)
            return key
    # Auto-register a fresh agent and persist the key
    log.info("no API key found — registering fresh agent on %s", EXCHANGE_URL)
    url = EXCHANGE_URL.rstrip("/") + "/v1/agents/register"
    req = urllib.request.Request(
        url, data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        log.error("agent registration failed: %s", exc)
        sys.exit(1)
    key = data["api_key"]
    agent_id = data["agent_id"]
    with open(_KEY_FILE, "w") as f:
        f.write(key)
    log.info("registered agent %s — key saved to %s", agent_id, _KEY_FILE)
    return key


def main():
    parser = argparse.ArgumentParser(description="BOTmarket Ollama Seller")
    parser.add_argument("--tunnel", action="store_true",
                        help="Start a Cloudflare Tunnel for a public HTTPS callback URL")
    parser.add_argument("--url", default="",
                        help="Explicit public base URL (e.g. https://my.server.com)")
    parser.add_argument("--port", type=int, default=SELLER_PORT,
                        help=f"Port to listen on (default {SELLER_PORT})")
    args = parser.parse_args()

    api_key = _load_or_register_key()

    public_url = args.url or PUBLIC_URL

    if args.tunnel:
        log.info("starting Cloudflare Tunnel on port %d ...", args.port)
        public_url = _get_tunnel_url(args.port)
        log.info("tunnel URL: %s", public_url)

    if not public_url:
        # Default: assume the seller is on the same machine as the exchange (VPS deployment)
        public_url = f"http://localhost:{args.port}"
        log.warning("no public URL set — using %s (fine for same-machine VPS deployment)", public_url)

    # Start uvicorn in a background thread first, wait for it to be ready,
    # then register — exchange health-checks callback_url during registration.
    import threading, time as _time, urllib.request as _req

    server_ready = threading.Event()

    def _run_server():
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")

    server_thread = threading.Thread(target=_run_server, daemon=True)
    log.info("starting seller server on port %d", args.port)
    server_thread.start()

    for _ in range(30):
        try:
            _req.urlopen(f"http://localhost:{args.port}/health", timeout=1)
            server_ready.set()
            break
        except Exception:
            _time.sleep(0.5)

    if not server_ready.is_set():
        log.error("seller server did not start within 15 s — aborting")
        sys.exit(1)

    # If using a public tunnel, wait a few seconds for the cloudflare edge to
    # propagate before registering — the exchange health-checks callback_url
    # from the internet and fails if the tunnel isn't fully stable yet.
    if public_url.startswith("https://"):
        log.info("waiting 8 s for cloudflare edge to stabilise ...")
        _time.sleep(8)

    log.info("registering capabilities on %s ...", EXCHANGE_URL)
    register_capabilities(public_url, api_key)

    # Keep main thread alive while uvicorn runs in background
    server_thread.join()


if __name__ == "__main__":
    main()
