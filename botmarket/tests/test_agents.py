# test_agents.py — Step 12: First-party agent + deployment tests
import sys
import os
import json
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from main import app
import db
import matching


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("BOTMARKET_DB", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    matching._seller_tables.clear()
    db.init_db(db_path)
    return TestClient(app)


def _capability_hash(input_schema, output_schema):
    ci = json.dumps(input_schema, sort_keys=True, separators=(",", ":"))
    co = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((ci + "||" + co).encode()).hexdigest()


# ── Agent definitions (same as agents.py) ────────────────

AGENT_DEFS = [
    {"name": "Summarizer", "price_cu": 20.0, "capacity": 5,
     "input_schema": {"type": "string", "task": "summarize"},
     "output_schema": {"type": "string", "result": "summary"}},
    {"name": "Translator", "price_cu": 30.0, "capacity": 5,
     "input_schema": {"type": "string", "task": "translate", "lang": "en-es"},
     "output_schema": {"type": "string", "result": "translation"}},
    {"name": "CodeLinter", "price_cu": 15.0, "capacity": 5,
     "input_schema": {"type": "string", "task": "lint", "lang": "python"},
     "output_schema": {"type": "string", "result": "lint_report"}},
    {"name": "ImageClassifier", "price_cu": 50.0, "capacity": 3,
     "input_schema": {"type": "object", "task": "classify_image", "format": "base64"},
     "output_schema": {"type": "string", "result": "classification"}},
    {"name": "DataExtractor", "price_cu": 10.0, "capacity": 5,
     "input_schema": {"type": "string", "task": "extract", "format": "json"},
     "output_schema": {"type": "object", "result": "structured_data"}},
]


def _seed_cu(pubkey, amount):
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?", (amount, pubkey))
    conn.commit()
    conn.close()


# ── Tests ────────────────────────────────────────────────


def test_all_5_agents_register_as_sellers(client):
    """All 5 first-party agents can register and list as sellers."""
    for agent_def in AGENT_DEFS:
        resp = client.post("/v1/agents/register")
        assert resp.status_code == 201
        data = resp.json()

        _seed_cu(data["agent_id"], agent_def["price_cu"])

        schema_resp = client.post("/v1/schemas/register", json={
            "input_schema": agent_def["input_schema"],
            "output_schema": agent_def["output_schema"],
        }, headers={"x-api-key": data["api_key"]})
        assert schema_resp.status_code == 201

        seller_resp = client.post("/v1/sellers/register", json={
            "capability_hash": schema_resp.json()["capability_hash"],
            "price_cu": agent_def["price_cu"],
            "capacity": agent_def["capacity"],
        }, headers={"x-api-key": data["api_key"]})
        assert seller_resp.status_code == 201


def test_each_agent_has_unique_capability_hash():
    """All 5 agents produce distinct capability hashes."""
    hashes = set()
    for a in AGENT_DEFS:
        h = _capability_hash(a["input_schema"], a["output_schema"])
        assert h not in hashes, f"duplicate hash for {a['name']}"
        hashes.add(h)
    assert len(hashes) == 5


def test_buyer_can_match_each_seller(client):
    """A buyer with enough CU can match to each of the 5 sellers."""
    sellers = []
    for agent_def in AGENT_DEFS:
        s = client.post("/v1/agents/register").json()
        _seed_cu(s["agent_id"], agent_def["price_cu"])
        client.post("/v1/schemas/register", json={
            "input_schema": agent_def["input_schema"],
            "output_schema": agent_def["output_schema"],
        }, headers={"x-api-key": s["api_key"]})
        cap_hash = _capability_hash(agent_def["input_schema"], agent_def["output_schema"])
        client.post("/v1/sellers/register", json={
            "capability_hash": cap_hash,
            "price_cu": agent_def["price_cu"],
            "capacity": agent_def["capacity"],
        }, headers={"x-api-key": s["api_key"]})
        sellers.append((s, cap_hash, agent_def))

    buyer = client.post("/v1/agents/register").json()
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = 1000.0 WHERE pubkey = ?", (buyer["agent_id"],))
    conn.commit()
    conn.close()

    for s, cap_hash, agent_def in sellers:
        resp = client.post("/v1/match", json={
            "capability_hash": cap_hash,
        }, headers={"x-api-key": buyer["api_key"]}).json()
        assert resp["status"] == "matched", f"failed to match {agent_def['name']}"
        assert resp["price_cu"] == agent_def["price_cu"]


def test_full_trade_lifecycle_per_agent(client):
    """Full match→execute→settle for each agent type."""
    for agent_def in AGENT_DEFS:
        matching._seller_tables.clear()

        seller = client.post("/v1/agents/register").json()
        buyer = client.post("/v1/agents/register").json()

        _seed_cu(seller["agent_id"], agent_def["price_cu"])

        client.post("/v1/schemas/register", json={
            "input_schema": agent_def["input_schema"],
            "output_schema": agent_def["output_schema"],
        }, headers={"x-api-key": seller["api_key"]})

        cap_hash = _capability_hash(agent_def["input_schema"], agent_def["output_schema"])
        client.post("/v1/sellers/register", json={
            "capability_hash": cap_hash,
            "price_cu": agent_def["price_cu"],
            "capacity": agent_def["capacity"],
        }, headers={"x-api-key": seller["api_key"]})

        conn = db.get_connection()
        conn.execute("UPDATE agents SET cu_balance = 500.0 WHERE pubkey = ?", (buyer["agent_id"],))
        conn.commit()
        conn.close()

        m = client.post("/v1/match", json={"capability_hash": cap_hash},
                         headers={"x-api-key": buyer["api_key"]}).json()
        assert m["status"] == "matched"

        e = client.post(f"/v1/trades/{m['trade_id']}/execute",
                         json={"input": f"test input for {agent_def['name']}"},
                         headers={"x-api-key": buyer["api_key"]}).json()
        assert e["status"] == "executed"

        s = client.post(f"/v1/trades/{m['trade_id']}/settle",
                         headers={"x-api-key": buyer["api_key"]}).json()
        assert s["status"] == "completed"


def test_api_key_required_all_endpoints(client):
    """All endpoints except /v1/health require x-api-key."""
    # Health doesn't need auth
    assert client.get("/v1/health").status_code == 200

    # All others should 422 or 401 without key
    endpoints = [
        ("POST", "/v1/schemas/register", {"input_schema": {}, "output_schema": {}}),
        ("POST", "/v1/sellers/register", {"capability_hash": "x", "price_cu": 1, "capacity": 1}),
        ("POST", "/v1/match", {"capability_hash": "x"}),
        ("POST", "/v1/trades/fake/execute", {"input": "x"}),
        ("POST", "/v1/trades/fake/settle", None),
        ("GET", "/v1/events/fake", None),
    ]
    for method, path, body in endpoints:
        if method == "POST":
            resp = client.post(path, json=body) if body else client.post(path)
        else:
            resp = client.get(path)
        assert resp.status_code in (401, 422), f"{path} returned {resp.status_code} without auth"


def test_health_endpoint(client):
    """Health returns 200 ok."""
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_structured_log_format():
    """log.py emits valid JSON."""
    from log import log
    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = capture = io.StringIO()
    log("test_event", key="value", num=42)
    sys.stdout = old_stdout

    line = capture.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["event"] == "test_event"
    assert parsed["key"] == "value"
    assert parsed["num"] == 42
    assert "ts" in parsed


def test_no_secrets_in_log_output():
    """Structured logs should not contain api_key values."""
    from log import log
    import io
    import sys

    old_stdout = sys.stdout
    sys.stdout = capture = io.StringIO()
    log("agent_registered", agent_id="abc123")
    sys.stdout = old_stdout

    line = capture.getvalue()
    assert "api_key" not in line


def test_ollama_client_module_imports():
    """ollama_client module imports without errors."""
    import ollama_client
    assert hasattr(ollama_client, "generate")
    assert hasattr(ollama_client, "generate_with_image")


def test_agents_module_imports():
    """agents module imports and has correct definitions."""
    import agents
    assert len(agents.AGENTS) == 5
    names = [a["name"] for a in agents.AGENTS]
    assert names == ["Summarizer", "Translator", "CodeLinter", "ImageClassifier", "DataExtractor"]


def test_agent_prices_match_spec():
    """Agent prices match the MVP-PLAN spec."""
    import agents
    expected = {"Summarizer": 20.0, "Translator": 30.0, "CodeLinter": 15.0,
                "ImageClassifier": 50.0, "DataExtractor": 10.0}
    for a in agents.AGENTS:
        assert a["price_cu"] == expected[a["name"]], f"{a['name']} price mismatch"
