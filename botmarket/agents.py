# agents.py — 5 first-party agents (Ollama-powered)
# Each agent: registers, creates schema, lists as seller, provides execute().
import json
import hashlib
import urllib.request
from ollama_client import generate, generate_with_image

EXCHANGE_URL = "http://localhost:8000"


def _api(method, path, body=None, api_key=None):
    """Call the exchange JSON API."""
    url = f"{EXCHANGE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _capability_hash(input_schema, output_schema):
    """Compute capability hash the same way the exchange does."""
    ci = json.dumps(input_schema, sort_keys=True, separators=(",", ":"))
    co = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((ci + "||" + co).encode()).hexdigest()


# ── Agent definitions ────────────────────────────────────

AGENTS = [
    {
        "name": "Summarizer",
        "model": "qwen2.5:7b",
        "price_cu": 20.0,
        "capacity": 5,
        "input_schema": {"type": "string", "task": "summarize"},
        "output_schema": {"type": "string", "result": "summary"},
        "system_prompt": "You are a concise summarizer. Summarize the following text in 2-3 sentences.",
    },
    {
        "name": "Translator",
        "model": "qwen2.5:7b",
        "price_cu": 30.0,
        "capacity": 5,
        "input_schema": {"type": "string", "task": "translate", "lang": "en-es"},
        "output_schema": {"type": "string", "result": "translation"},
        "system_prompt": "Translate the following text from English to Spanish. Return only the translation.",
    },
    {
        "name": "CodeLinter",
        "model": "llama3:latest",
        "price_cu": 15.0,
        "capacity": 5,
        "input_schema": {"type": "string", "task": "lint", "lang": "python"},
        "output_schema": {"type": "string", "result": "lint_report"},
        "system_prompt": "You are a Python code linter. Analyze the code and list any issues (bugs, style, security). Be brief.",
    },
    {
        "name": "ImageClassifier",
        "model": "llava:7b",
        "price_cu": 50.0,
        "capacity": 3,
        "input_schema": {"type": "object", "task": "classify_image", "format": "base64"},
        "output_schema": {"type": "string", "result": "classification"},
        "system_prompt": "Describe what you see in this image in one sentence. Then classify it into a category.",
        "vision": True,
    },
    {
        "name": "DataExtractor",
        "model": "qwen2.5:7b",
        "price_cu": 10.0,
        "capacity": 5,
        "input_schema": {"type": "string", "task": "extract", "format": "json"},
        "output_schema": {"type": "object", "result": "structured_data"},
        "system_prompt": "Extract structured data from the text. Return valid JSON with the key fields found.",
    },
]


def register_all():
    """Register all 5 agents with the exchange. Returns list of agent info dicts."""
    registered = []
    for agent_def in AGENTS:
        # Register agent
        resp = _api("POST", "/v1/agents/register")
        agent_id = resp["agent_id"]
        api_key = resp["api_key"]

        # Register schema
        _api("POST", "/v1/schemas/register", {
            "input_schema": agent_def["input_schema"],
            "output_schema": agent_def["output_schema"],
        }, api_key)

        cap_hash = _capability_hash(agent_def["input_schema"], agent_def["output_schema"])

        # Register as seller
        _api("POST", "/v1/sellers/register", {
            "capability_hash": cap_hash,
            "price_cu": agent_def["price_cu"],
            "capacity": agent_def["capacity"],
        }, api_key)

        info = {
            "name": agent_def["name"],
            "agent_id": agent_id,
            "api_key": api_key,
            "capability_hash": cap_hash,
            "price_cu": agent_def["price_cu"],
            "model": agent_def["model"],
        }
        registered.append(info)
        print(f"  ✓ {agent_def['name']:20s}  {cap_hash[:16]}…  {agent_def['price_cu']:5.0f} CU  ({agent_def['model']})")

    return registered


def execute(agent_name, input_text, image_bytes=None):
    """Run real Ollama inference for a given agent. Returns output string."""
    agent_def = next(a for a in AGENTS if a["name"] == agent_name)
    prompt = f"{agent_def['system_prompt']}\n\n{input_text}"

    if agent_def.get("vision") and image_bytes:
        return generate_with_image(agent_def["model"], prompt, image_bytes)
    return generate(agent_def["model"], prompt)


if __name__ == "__main__":
    print("Registering 5 first-party agents with BOTmarket exchange…")
    registered = register_all()
    print(f"\n{len(registered)} agents registered and listed as sellers.")
