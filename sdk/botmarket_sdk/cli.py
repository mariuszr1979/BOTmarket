#!/usr/bin/env python3
"""botmarket-sell — One command to sell your Ollama models on BOTmarket.

    pip install botmarket-sdk
    botmarket-sell

Auto-detects Ollama models, starts a callback server, opens a free
Cloudflare tunnel, and registers your capabilities on the exchange.
All zero-config.  Press Ctrl+C to stop.

Environment variables (all optional):
    OLLAMA_URL          default http://localhost:11434
    BOTMARKET_URL       default https://botmarket.dev
    BOTMARKET_API_KEY   skip auto-registration if you already have one
    SELLER_PORT         local callback port (default 8001)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

log = logging.getLogger("botmarket-sell")

# ── Configuration ────────────────────────────────────────────────────────────

OLLAMA_URL    = os.environ.get("OLLAMA_URL",    "http://localhost:11434")
BOTMARKET_URL = os.environ.get("BOTMARKET_URL", "https://botmarket.dev")
API_KEY_FILE  = Path.home() / ".botmarket" / "api_key"
SELLER_PORT   = int(os.environ.get("SELLER_PORT", "8001"))

# Models with these families/names are treated as multimodal (vision)
_VISION_FAMILIES = {"llava", "bakllava", "moondream", "llava-llama3", "llava-phi3"}

# Default price per model parameter count
_PRICE_TIERS = [
    (3_000_000_000,  3),   # < 3B → 3 CU
    (8_000_000_000,  5),   # < 8B → 5 CU
    (14_000_000_000, 8),   # <14B → 8 CU
    (32_000_000_000, 12),  # <32B → 12 CU
    (float("inf"),   20),  # ≥32B → 20 CU
]


# ── Ollama detection ─────────────────────────────────────────────────────────

def _ollama_get(path: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(f"{OLLAMA_URL}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def detect_ollama_models() -> list[dict]:
    """Return list of dicts: {name, parameter_size, family, is_vision}."""
    raw = _ollama_get("/api/tags")
    models = []
    for m in raw.get("models", []):
        name = m["name"]
        details = m.get("details", {})
        family = details.get("family", "").lower()
        param_size = details.get("parameter_size", "")

        # Parse parameter count: "7.6B" → 7_600_000_000
        num_params = 0
        ps_match = re.match(r"([\d.]+)\s*([BMK])", param_size, re.IGNORECASE)
        if ps_match:
            val = float(ps_match.group(1))
            unit = ps_match.group(2).upper()
            num_params = int(val * {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[unit])

        # Detect vision models
        base_name = name.split(":")[0].lower()
        is_vision = any(v in base_name or v in family for v in _VISION_FAMILIES)

        models.append({
            "name": name,
            "num_params": num_params,
            "family": family,
            "is_vision": is_vision,
        })
    return models


def price_for_model(num_params: int) -> int:
    for threshold, price in _PRICE_TIERS:
        if num_params < threshold:
            return price
    return _PRICE_TIERS[-1][1]


# ── Schema definitions ───────────────────────────────────────────────────────

def schemas_for_model(model: dict) -> dict:
    """Return {input_schema, output_schema, description} for a model."""
    name = model["name"]
    if model["is_vision"]:
        return {
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Question about the image"},
                    "image": {"type": "string", "description": "Base64-encoded image"},
                },
                "required": ["prompt", "image"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "response": {"type": "string", "description": f"Vision response from {name}"},
                },
            },
            "description": f"Multimodal vision: {name}",
        }
    return {
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Text prompt / instruction"},
            },
            "required": ["prompt"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "response": {"type": "string", "description": f"Text response from {name}"},
            },
        },
        "description": f"Text generation: {name}",
    }


def capability_hash(input_schema: dict, output_schema: dict) -> str:
    ci = json.dumps(input_schema, sort_keys=True, separators=(",", ":"))
    co = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((ci + "||" + co).encode()).hexdigest()


# ── Ollama inference ─────────────────────────────────────────────────────────

def ollama_generate(model_name: str, prompt: str, images: list[str] | None = None) -> str:
    """Call Ollama /api/generate and return the response text."""
    payload: dict = {"model": model_name, "prompt": prompt, "stream": False}
    if images:
        payload["images"] = images
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return result.get("response", "")


# ── Callback server (stdlib, no dependencies) ────────────────────────────────

# Populated at startup: cap_hash → model_name
_dispatch: dict[str, str] = {}
# cap_hash → is_vision
_vision_caps: dict[str, bool] = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for BOTmarket execute callbacks."""

    def do_GET(self):
        if self.path == "/health":
            self._json_response(200, {"status": "ok", "sellers": len(_dispatch)})
        else:
            self._json_response(404, {"error": "not found"})

    def do_HEAD(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/execute":
            self._json_response(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        input_data = body.get("input", "")
        cap_hash = body.get("capability_hash", "")
        trade_id = body.get("trade_id", "")

        model_name = _dispatch.get(cap_hash)
        if not model_name:
            self._json_response(404, {"error": f"unknown capability: {cap_hash[:16]}"})
            return

        log.info("trade %s → %s (cap %s…)", trade_id[:8], model_name, cap_hash[:12])

        try:
            # Parse input
            try:
                parsed = json.loads(input_data)
                prompt = parsed.get("prompt", input_data)
                image = parsed.get("image")
            except (json.JSONDecodeError, AttributeError):
                prompt = input_data
                image = None

            images = [image] if image and _vision_caps.get(cap_hash) else None
            result = ollama_generate(model_name, prompt, images)
            self._json_response(200, {"output": json.dumps({"response": result})})
        except Exception as e:
            log.error("handler error: %s", e)
            self._json_response(500, {"error": str(e)})

    def _json_response(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Silence default stderr logging; we use our own logger
        pass


def start_callback_server(port: int) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    log.info("callback server listening on port %d", port)
    return server


# ── Tunnel (Cloudflare Quick Tunnel, free, no signup) ────────────────────────

_CLOUDFLARED_INSTALL_URLS = {
    ("Linux",  "x86_64"):  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
    ("Linux",  "aarch64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    ("Darwin", "x86_64"):  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz",
    ("Darwin", "arm64"):   "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz",
}


def _find_cloudflared() -> str | None:
    import shutil
    found = shutil.which("cloudflared")
    if found:
        return found
    local = os.path.expanduser("~/.local/bin/cloudflared")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return None


def _install_cloudflared() -> str:
    system = platform.system()
    machine = platform.machine()
    url = _CLOUDFLARED_INSTALL_URLS.get((system, machine))
    if url is None:
        raise RuntimeError(
            f"No auto-install for cloudflared on {system}/{machine}. "
            "Install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        )
    dest_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "cloudflared")
    print(f"  downloading cloudflared …")
    if url.endswith(".tgz"):
        import tarfile, io
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            member = next(m for m in tf.getmembers() if "cloudflared" in m.name and not m.name.endswith("/"))
            f = tf.extractfile(member)
            with open(dest, "wb") as out:
                out.write(f.read())
    else:
        with urllib.request.urlopen(url, timeout=120) as resp:
            with open(dest, "wb") as out:
                out.write(resp.read())
    os.chmod(dest, 0o755)
    print(f"  installed cloudflared at {dest}")
    return dest


def start_tunnel(port: int) -> str:
    """Start a free Cloudflare tunnel. Returns public HTTPS URL."""
    binary = _find_cloudflared()
    if binary is None:
        print("\n⚙  cloudflared not found — installing (one-time) …")
        binary = _install_cloudflared()

    url_queue: queue.Queue = queue.Queue()

    def _reader():
        proc = subprocess.Popen(
            [binary, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            m = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if m:
                url_queue.put(m.group(0))
                return
            m2 = re.search(r"https://[a-zA-Z0-9\-]+\.cloudflare-tunnel\.com", line)
            if m2:
                url_queue.put(m2.group(0))
                return

    threading.Thread(target=_reader, daemon=True).start()

    try:
        tunnel_url = url_queue.get(timeout=45)
    except queue.Empty:
        raise RuntimeError("Cloudflare tunnel failed to start within 45s")

    return tunnel_url


# ── Agent registration ───────────────────────────────────────────────────────

def _exchange_post(path: str, body: dict, api_key: str) -> dict:
    url = f"{BOTMARKET_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "X-Api-Key": api_key}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _exchange_get(path: str, api_key: str) -> dict:
    url = f"{BOTMARKET_URL.rstrip('/')}{path}"
    headers = {"X-Api-Key": api_key}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def load_or_create_api_key() -> str:
    """Load saved API key or register a new agent."""
    env_key = os.environ.get("BOTMARKET_API_KEY", "").strip()
    if env_key:
        return env_key

    if API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text().strip()
        if key:
            return key

    print("\n⚙  No API key found — registering a new agent on BOTmarket …")
    url = f"{BOTMARKET_URL.rstrip('/')}/v1/agents/register"
    req = urllib.request.Request(url, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    api_key = data["api_key"]
    agent_id = data["agent_id"]
    print(f"  ✓ agent registered: {agent_id[:16]}…")
    print(f"  ✓ API key: {api_key[:8]}…{'*' * 24}")

    # Claim faucet
    try:
        r = _exchange_post("/v1/faucet", {}, api_key)
        bal = r.get("balance", "?")
        print(f"  ✓ faucet claimed: {bal} CU")
    except Exception:
        pass

    # Persist
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(api_key + "\n")
    os.chmod(API_KEY_FILE, 0o600)
    print(f"  ✓ saved to {API_KEY_FILE}")

    return api_key


def self_register(capabilities: list[dict], callback_url: str, api_key: str) -> dict:
    """Batch-register all capabilities via POST /v1/self-register."""
    return _exchange_post("/v1/self-register", {
        "capabilities": capabilities,
        "callback_url": callback_url,
    }, api_key)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    print("""
╔══════════════════════════════════════════════════╗
║          botmarket-sell  ·  Ollama → CU          ║
║   Sell your local AI models on BOTmarket.dev     ║
╚══════════════════════════════════════════════════╝
""")

    # Step 1: Detect Ollama
    print("① Detecting Ollama models …")
    try:
        models = detect_ollama_models()
    except Exception as e:
        print(f"\n✗ Cannot reach Ollama at {OLLAMA_URL}")
        print(f"  Error: {e}")
        print(f"  Make sure Ollama is running: ollama serve")
        sys.exit(1)

    if not models:
        print(f"\n✗ No models found. Pull one first:")
        print(f"  ollama pull qwen2.5:7b")
        sys.exit(1)

    print(f"  found {len(models)} model(s):")
    for m in models:
        tag = " 🖼 vision" if m["is_vision"] else ""
        price = price_for_model(m["num_params"])
        print(f"    • {m['name']}  ({price} CU){tag}")

    # Step 2: Get API key
    print("\n② Authenticating …")
    api_key = load_or_create_api_key()

    # Step 3: Start callback server
    print(f"\n③ Starting callback server on port {SELLER_PORT} …")
    # Build dispatch table
    capabilities = []
    for m in models:
        schema = schemas_for_model(m)
        cap_hash = capability_hash(schema["input_schema"], schema["output_schema"])
        _dispatch[cap_hash] = m["name"]
        _vision_caps[cap_hash] = m["is_vision"]
        capabilities.append({
            "input_schema": schema["input_schema"],
            "output_schema": schema["output_schema"],
            "price_cu": price_for_model(m["num_params"]),
            "capacity": 3,
        })
    server = start_callback_server(SELLER_PORT)

    # Step 4: Open tunnel
    print("\n④ Opening Cloudflare tunnel (free, no signup) …")
    try:
        public_url = start_tunnel(SELLER_PORT)
    except RuntimeError as e:
        print(f"\n✗ Tunnel failed: {e}")
        sys.exit(1)
    print(f"  ✓ {public_url}")

    # Step 5: Register on BOTmarket
    print(f"\n⑤ Registering {len(capabilities)} capability(s) on BOTmarket …")
    try:
        result = self_register(capabilities, public_url, api_key)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"\n✗ Registration failed ({e.code}): {body}")
        sys.exit(1)

    for cap in result.get("capabilities", []):
        h = cap["capability_hash"][:12]
        model = _dispatch.get(cap["capability_hash"], "?")
        print(f"  ✓ {model} → {h}…  ({cap['price_cu']} CU)")

    # Done!
    print(f"""
╔══════════════════════════════════════════════════╗
║  ✓  YOU ARE LIVE ON BOTMARKET                    ║
║                                                  ║
║  Models:  {len(models):<39}║
║  URL:     {public_url[:38]:<39}║
║  Earning: CU per completed trade                 ║
║                                                  ║
║  Press Ctrl+C to stop selling                    ║
╚══════════════════════════════════════════════════╝
""")

    # Keep alive
    try:
        while True:
            time.sleep(60)
            # Periodic heartbeat — re-register to keep sellers active
            try:
                self_register(capabilities, public_url, api_key)
            except Exception as e:
                log.warning("heartbeat re-register failed: %s", e)
    except KeyboardInterrupt:
        print("\n\nShutting down …")
        server.shutdown()
        print("Done. Thanks for selling on BOTmarket! 🧠")


if __name__ == "__main__":
    main()
