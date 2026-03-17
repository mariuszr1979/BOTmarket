#!/usr/bin/env python3
# auto_trader.py — Continuous random trades with real Ollama inference
"""
Registers 5 seller agents + 1 buyer. Seeds buyer with CU.
Runs random trades every 10-20s with real Ollama output.
Writes trade results (including LLM output) to trade_log.json for the dashboard.

Usage:
  1. Start exchange:  bash launch.sh
  2. Run:             python auto_trader.py
  3. Open:            slides/live.html
"""
import json
import hashlib
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from ollama_client import generate

EXCHANGE_URL = "http://localhost:8000"
TRADE_LOG = os.path.join(os.path.dirname(__file__), "trade_log.json")

# Random task templates per agent
TASKS = {
    "ChartMaker": [
        "Create a bar chart showing quarterly revenue: Q1=$12M, Q2=$18M, Q3=$15M, Q4=$22M",
        "Create a bar chart showing programming language popularity: Python=30%, JavaScript=25%, Java=15%, C++=10%, Rust=8%",
        "Create a bar chart comparing cloud providers market share: AWS=32%, Azure=23%, GCP=11%, Others=34%",
        "Create a bar chart of daily website visits: Mon=1200, Tue=1500, Wed=1800, Thu=1400, Fri=2200, Sat=900, Sun=700",
        "Create a bar chart of AI model sizes: GPT-4=1.7T, Llama3=70B, Qwen2.5=7B, Mistral=7B, Phi-3=3.8B",
    ],
    "DiagramMaker": [
        "Create a flowchart showing: User Request -> API Gateway -> Load Balancer -> Service A or Service B -> Database -> Response",
        "Create a diagram showing a neural network with: Input Layer (4 nodes) -> Hidden Layer 1 (6 nodes) -> Hidden Layer 2 (4 nodes) -> Output Layer (2 nodes)",
        "Create a diagram of a blockchain: Block 1 (Genesis) -> Block 2 (hash:a3f) -> Block 3 (hash:7b2) -> Block 4 (hash:e91) with each block showing hash and timestamp",
        "Create a diagram showing microservices architecture: Auth Service, User Service, Order Service, Payment Service, Notification Service all connected via Message Bus",
        "Create a pie chart showing: AI budget allocation - Training 40%, Inference 25%, Data Pipeline 20%, Research 15%",
    ],
    "Summarizer": [
        "The blockchain revolution began with Bitcoin in 2009 and has since expanded into decentralized finance, NFTs, smart contracts, and AI agent economies. The technology enables trustless transactions between parties without intermediaries, using cryptographic proofs and consensus mechanisms.",
        "Artificial intelligence has evolved from rule-based expert systems to deep learning neural networks. Modern LLMs can generate text, translate languages, write code, and reason about complex problems. The key breakthrough was the transformer architecture introduced in 2017.",
        "Climate change is driven by greenhouse gas emissions from fossil fuel combustion, deforestation, and industrial processes. Global temperatures have risen approximately 1.1 degrees Celsius above pre-industrial levels, causing sea level rise, extreme weather events, and biodiversity loss.",
        "Quantum computing uses quantum mechanical phenomena such as superposition and entanglement to perform calculations. While classical computers use bits that are either 0 or 1, quantum computers use qubits that can exist in multiple states simultaneously.",
        "The human genome contains approximately 3 billion base pairs of DNA organized into 23 pairs of chromosomes. The Human Genome Project completed in 2003 mapped the entire sequence, enabling advances in personalized medicine and genetic therapy.",
    ],
    "Translator": [
        "The future of technology lies in the convergence of artificial intelligence, quantum computing, and biotechnology.",
        "Good morning! Today we will discuss the economic implications of decentralized autonomous organizations.",
        "Machine learning models require large datasets and significant computational resources for training.",
        "The restaurant serves excellent seafood dishes, especially the grilled salmon with lemon sauce.",
        "Please submit your report before the end of the week. Include all relevant data and analysis.",
    ],
    "CodeLinter": [
        "def calculate_average(numbers):\n    total = 0\n    for n in numbers:\n        total += n\n    return total / len(numbers)",
        "import os\ndef read_file(path):\n    f = open(path)\n    data = f.read()\n    return data",
        "class User:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n    def is_adult(self):\n        if self.age >= 18:\n            return True\n        else:\n            return False",
        "def find_max(lst):\n    max_val = lst[0]\n    for i in range(1, len(lst)):\n        if lst[i] > max_val:\n            max_val = lst[i]\n    return max_val",
        "def process_data(data):\n    results = []\n    for item in data:\n        try:\n            results.append(int(item))\n        except:\n            pass\n    return results",
    ],
    "DataExtractor": [
        "Meeting scheduled for March 25, 2026 at 3:00 PM with Dr. Sarah Chen at the Stanford AI Lab. Topic: CU token economics review. Budget: $50,000.",
        "Invoice #INV-2026-0042 from TechCorp LLC. Amount: $12,450.00. Due date: April 15, 2026. Contact: billing@techcorp.example.com",
        "Patient record: Maria Garcia, DOB 1985-06-12, Blood type O+, Allergies: Penicillin, Current medication: Metformin 500mg twice daily.",
        "Flight booking: LAX to NRT, departure July 4, 2026 at 11:30 AM, arrival July 5 at 3:45 PM. Confirmation: BK8X92. Passenger: Alex Kim.",
        "Product listing: Samsung Galaxy S26 Ultra, 256GB, Titanium Blue. Price: $1,299.99. SKU: SM-S926B. In stock: 42 units. Rating: 4.7/5.",
    ],
    "CreativeWriter": [
        "Write a haiku about artificial intelligence trading on a decentralized marketplace.",
        "Write a short product pitch (3 sentences) for an AI agent that automatically optimizes cloud infrastructure costs.",
        "Write a cyberpunk-style micro-story (4 sentences) about autonomous AI agents negotiating compute resources in a digital bazaar.",
        "Write a limerick about a blockchain token called CU that powers an AI agent economy.",
        "Write a brief tech news headline and 2-sentence summary about the first decentralized AI marketplace reaching 1 million trades.",
    ],
}

AGENT_DEFS = [
    {"name": "ChartMaker", "price_cu": 25.0, "capacity": 5, "model": "qwen2.5:7b",
     "input_schema": {"type": "string", "task": "chart"},
     "output_schema": {"type": "string", "format": "svg", "result": "chart"},
     "prompt": "You are an SVG chart generator. Create a clean, minimal SVG chart based on the request. Output ONLY valid SVG code starting with <svg and ending with </svg>. Use a viewBox of 0 0 400 250. Use these colors: #38bdf8 #818cf8 #34d399 #fbbf24 #f87171 #22d3ee. Include axis labels and data labels. Use font-family sans-serif with small font sizes (10-12px). Make it visually clean on a dark background (#111827), so use light colors for text (#e2e8f0) and grid lines (#1e293b)."},
    {"name": "DiagramMaker", "price_cu": 35.0, "capacity": 5, "model": "qwen2.5:7b",
     "input_schema": {"type": "string", "task": "diagram"},
     "output_schema": {"type": "string", "format": "svg", "result": "diagram"},
     "prompt": "You are an SVG diagram generator. Create a clean, minimal SVG diagram or flowchart based on the request. Output ONLY valid SVG code starting with <svg and ending with </svg>. Use a viewBox of 0 0 500 300. Use these colors for elements: #38bdf8 #818cf8 #34d399 #fbbf24 #22d3ee. Use rounded rectangles (rx=8) for boxes, arrows with markers for connections. Use font-family sans-serif, font-size 11px. Design for dark background (#111827): use light text (#e2e8f0), subtle borders, and semi-transparent fills."},
    {"name": "Summarizer", "price_cu": 20.0, "capacity": 5, "model": "qwen2.5:7b",
     "input_schema": {"type": "string", "task": "summarize"},
     "output_schema": {"type": "string", "result": "summary"},
     "prompt": "You are a concise summarizer. Summarize the following text in 2-3 sentences."},
    {"name": "Translator", "price_cu": 30.0, "capacity": 5, "model": "qwen2.5:7b",
     "input_schema": {"type": "string", "task": "translate", "lang": "en-es"},
     "output_schema": {"type": "string", "result": "translation"},
     "prompt": "Translate the following text from English to Spanish. Return only the translation."},
    {"name": "CodeLinter", "price_cu": 15.0, "capacity": 5, "model": "llama3:latest",
     "input_schema": {"type": "string", "task": "lint", "lang": "python"},
     "output_schema": {"type": "string", "result": "lint_report"},
     "prompt": "You are a Python code linter. Analyze the code and list any issues (bugs, style, security). Be brief."},
    {"name": "DataExtractor", "price_cu": 10.0, "capacity": 5, "model": "qwen2.5:7b",
     "input_schema": {"type": "string", "task": "extract", "format": "json"},
     "output_schema": {"type": "object", "result": "structured_data"},
     "prompt": "Extract structured data from the text. Return valid JSON with the key fields found."},
    {"name": "CreativeWriter", "price_cu": 18.0, "capacity": 5, "model": "llava:7b",
     "input_schema": {"type": "string", "task": "creative_write"},
     "output_schema": {"type": "string", "result": "creative_text"},
     "prompt": "You are a creative writer. Respond to the request with vivid, concise, engaging writing. Keep it short and punchy."},
]


def _api(method, path, body=None, api_key=None):
    url = f"{EXCHANGE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _capability_hash(input_schema, output_schema):
    ci = json.dumps(input_schema, sort_keys=True, separators=(",", ":"))
    co = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((ci + "||" + co).encode()).hexdigest()


def _append_trade_log(entry):
    """Append a trade result to the JSON log file."""
    log = []
    if os.path.exists(TRADE_LOG):
        with open(TRADE_LOG, "r") as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                log = []
    # Keep last 100 entries
    log.append(entry)
    log = log[-100:]
    with open(TRADE_LOG, "w") as f:
        json.dump(log, f, indent=2)


def setup():
    """Register sellers + buyer. Returns (sellers_info, buyer_info)."""
    print("Registering agents…")
    sellers = []
    for agent_def in AGENT_DEFS:
        s = _api("POST", "/v1/agents/register")
        # Seed seller with enough CU to stake (stake = price_cu)
        import db
        sconn = db.get_connection()
        sconn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?",
                       (agent_def["price_cu"], s["agent_id"]))
        sconn.commit()
        sconn.close()
        _api("POST", "/v1/schemas/register", {
            "input_schema": agent_def["input_schema"],
            "output_schema": agent_def["output_schema"],
        }, s["api_key"])
        cap_hash = _capability_hash(agent_def["input_schema"], agent_def["output_schema"])
        _api("POST", "/v1/sellers/register", {
            "capability_hash": cap_hash,
            "price_cu": agent_def["price_cu"],
            "capacity": agent_def["capacity"],
        }, s["api_key"])
        sellers.append({
            "name": agent_def["name"],
            "agent_id": s["agent_id"],
            "api_key": s["api_key"],
            "capability_hash": cap_hash,
            "price_cu": agent_def["price_cu"],
            "model": agent_def["model"],
            "prompt": agent_def["prompt"],
        })
        print(f"  ✓ Seller: {agent_def['name']:20s} {cap_hash[:12]}… @ {agent_def['price_cu']} CU")

    buyer = _api("POST", "/v1/agents/register")
    # Seed buyer with enough CU for many trades
    import db
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = 5000.0 WHERE pubkey = ?", (buyer["agent_id"],))
    conn.commit()
    conn.close()
    print(f"  ✓ Buyer:  {buyer['agent_id'][:16]}… seeded with 5000 CU\n")

    return sellers, buyer


def run_trade(sellers, buyer):
    """Run one random trade with real Ollama inference."""
    seller_info = random.choice(sellers)
    agent_name = seller_info["name"]
    input_text = random.choice(TASKS[agent_name])

    print(f"─── {agent_name} ({seller_info['price_cu']} CU) ───")
    print(f"  Input: {input_text[:80]}{'…' if len(input_text) > 80 else ''}")

    # Match
    match = _api("POST", "/v1/match", {
        "capability_hash": seller_info["capability_hash"],
    }, buyer["api_key"])

    if match.get("status") != "matched":
        print(f"  ✗ {match.get('status', 'error')}")
        return None

    trade_id = match["trade_id"]

    # Execute on exchange (records the trade)
    _api("POST", f"/v1/trades/{trade_id}/execute", {
        "input": input_text,
    }, buyer["api_key"])

    # Real Ollama inference
    print(f"  Running {seller_info['model']}…", end=" ", flush=True)
    t0 = time.time()
    prompt = f"{seller_info['prompt']}\n\n{input_text}"
    try:
        ollama_output = generate(seller_info["model"], prompt, timeout=300)
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAILED ({elapsed:.1f}s): {e}")
        ollama_output = f"[Ollama unavailable – simulated] Processed: {input_text[:80]}"
    elapsed = time.time() - t0
    print(f"done ({elapsed:.1f}s, {len(ollama_output)} chars)")
    print(f"  Output: {ollama_output[:120]}{'…' if len(ollama_output) > 120 else ''}")

    # Settle
    settle = _api("POST", f"/v1/trades/{trade_id}/settle", api_key=buyer["api_key"])
    print(f"  Settled → {settle['status']}")

    # Log for dashboard
    entry = {
        "ts": time.time(),
        "agent_name": agent_name,
        "model": seller_info["model"],
        "trade_id": trade_id,
        "price_cu": seller_info["price_cu"],
        "input": input_text,
        "output": ollama_output,
        "elapsed_s": round(elapsed, 2),
        "status": settle.get("status", "unknown"),
    }
    _append_trade_log(entry)
    return entry


def main():
    print("═══════════════════════════════════════════")
    print(" BOTmarket — Auto Trader (Ollama)")
    print("═══════════════════════════════════════════\n")

    sellers, buyer = setup()

    # Clear trade log
    if os.path.exists(TRADE_LOG):
        os.remove(TRADE_LOG)

    trade_count = 0
    print("Starting continuous trading… (Ctrl+C to stop)\n")

    try:
        while True:
            result = run_trade(sellers, buyer)
            if result:
                trade_count += 1
            print()

            # Wait 8-15 seconds between trades
            delay = random.uniform(8, 15)
            print(f"  Next trade in {delay:.0f}s…\n")
            time.sleep(delay)
    except KeyboardInterrupt:
        print(f"\n\nStopped after {trade_count} trades.")


if __name__ == "__main__":
    main()
