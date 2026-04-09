# tests/test_callbacks.py — Step 2: Real Seller Callbacks tests
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest
from starlette.testclient import TestClient

from main import app

SAMPLE_INPUT = {"type": "object", "properties": {"text": {"type": "string"}}}
SAMPLE_OUTPUT = {"type": "object", "properties": {"result": {"type": "string"}}}


@pytest.fixture
def client(db_setup):
    with TestClient(app) as c:
        yield c


def _register(client):
    resp = client.post("/v1/agents/register")
    data = resp.json()
    return data["agent_id"], data["api_key"]


def _setup_schema(client, api_key):
    return client.post(
        "/v1/schemas/register",
        json={"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT},
        headers={"X-API-Key": api_key},
    ).json()["capability_hash"]


def _fund(pubkey, amount):
    from db import get_connection
    conn = get_connection()
    conn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?", (amount, pubkey))
    conn.commit()
    conn.close()


class MockSellerHandler(BaseHTTPRequestHandler):
    """Mock HTTP seller that returns configurable responses."""

    # Class-level config — set before each test
    response_body = {"output": "mock result"}
    response_status = 200
    response_delay = 0  # seconds
    last_request_body = None
    last_headers = {}
    call_count = 0

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        MockSellerHandler.call_count += 1
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b""
        MockSellerHandler.last_request_body = json.loads(body) if body else None
        MockSellerHandler.last_headers = dict(self.headers)

        if MockSellerHandler.response_delay > 0:
            time.sleep(MockSellerHandler.response_delay)

        self.send_response(MockSellerHandler.response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(MockSellerHandler.response_body).encode())

    def log_message(self, format, *args):
        pass  # Suppress HTTP server log output


@pytest.fixture
def mock_seller():
    """Start a mock HTTP server on localhost, return its URL."""
    MockSellerHandler.response_body = {"output": "mock result"}
    MockSellerHandler.response_status = 200
    MockSellerHandler.response_delay = 0
    MockSellerHandler.last_request_body = None
    MockSellerHandler.last_headers = {}
    MockSellerHandler.call_count = 0

    server = HTTPServer(("127.0.0.1", 0), MockSellerHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# ── Seller registration with callback_url ──────────────


class TestSellerRegistration:
    """callback_url handling in seller registration."""

    def test_register_with_callback_url(self, client, mock_seller):
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        resp = client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": mock_seller,
        }, headers={"X-API-Key": skey})
        assert resp.status_code == 201

    def test_register_without_callback_url(self, client):
        """Legacy: no callback_url → still works (simulated execution)."""
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        resp = client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
        }, headers={"X-API-Key": skey})
        assert resp.status_code == 201

    def test_callback_url_health_check_fails(self, client):
        """Unreachable callback_url → 400 at registration."""
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        resp = client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": "http://127.0.0.1:1",  # unlikely to be listening
        }, headers={"X-API-Key": skey})
        assert resp.status_code == 400
        assert "unreachable" in resp.json()["detail"]

    def test_invalid_callback_url_scheme(self, client):
        """Non-HTTP scheme → 400."""
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        resp = client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": "ftp://evil.com/payload",
        }, headers={"X-API-Key": skey})
        assert resp.status_code == 400
        assert "http or https" in resp.json()["detail"]

    def test_callback_url_stored_in_db(self, client, mock_seller):
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": mock_seller,
        }, headers={"X-API-Key": skey})
        from db import get_connection
        conn = get_connection()
        row = conn.execute("SELECT callback_url FROM sellers WHERE agent_pubkey = ?", (sid,)).fetchone()
        conn.close()
        assert row["callback_url"] == mock_seller


# ── Trade execution with real callbacks ─────────────────


class TestRealCallback:
    """Trade execution calls seller URL and returns real output."""

    def _setup_trade(self, client, mock_seller, seller_callback_url=None):
        """Full setup: seller + buyer + schema + match. Returns (buyer_key, trade_id)."""
        sid, skey = _register(client)
        bid, bkey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        _fund(bid, 1000)
        url = seller_callback_url or mock_seller
        client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": url,
        }, headers={"X-API-Key": skey})
        trade = client.post("/v1/match", json={"capability_hash": cap},
                            headers={"X-API-Key": bkey}).json()
        return bkey, trade["trade_id"], bid, sid

    def test_callback_returns_output(self, client, mock_seller):
        MockSellerHandler.response_body = {"output": "real AI result"}
        bkey, trade_id, _, _ = self._setup_trade(client, mock_seller)
        resp = client.post(f"/v1/trades/{trade_id}/execute",
                           json={"input": "hello"},
                           headers={"X-API-Key": bkey})
        assert resp.status_code == 200
        assert resp.json()["status"] == "executed"
        assert resp.json()["output"] == "real AI result"

    def test_callback_receives_correct_payload(self, client, mock_seller):
        MockSellerHandler.response_body = {"output": "ok"}
        bkey, trade_id, _, _ = self._setup_trade(client, mock_seller)
        client.post(f"/v1/trades/{trade_id}/execute",
                    json={"input": "test input"},
                    headers={"X-API-Key": bkey})
        assert MockSellerHandler.last_request_body["input"] == "test input"
        assert MockSellerHandler.last_request_body["trade_id"] == trade_id
        assert "capability_hash" in MockSellerHandler.last_request_body

    def test_callback_receives_trade_headers(self, client, mock_seller):
        MockSellerHandler.response_body = {"output": "ok"}
        bkey, trade_id, _, _ = self._setup_trade(client, mock_seller)
        client.post(f"/v1/trades/{trade_id}/execute",
                    json={"input": "test"},
                    headers={"X-API-Key": bkey})
        assert MockSellerHandler.last_headers.get("X-Trade-Id") == trade_id
        assert "X-Capability-Hash" in MockSellerHandler.last_headers

    def test_no_buyer_identity_leaked(self, client, mock_seller):
        """Exchange never forwards buyer identity to seller (privacy)."""
        MockSellerHandler.response_body = {"output": "ok"}
        bkey, trade_id, bid, _ = self._setup_trade(client, mock_seller)
        client.post(f"/v1/trades/{trade_id}/execute",
                    json={"input": "test"},
                    headers={"X-API-Key": bkey})
        body = MockSellerHandler.last_request_body
        headers = MockSellerHandler.last_headers
        # Buyer pubkey should not appear anywhere in the callback
        body_str = json.dumps(body)
        assert bid not in body_str
        assert bid not in str(headers)

    def test_latency_measured_accurately(self, client, mock_seller):
        MockSellerHandler.response_body = {"output": "ok"}
        bkey, trade_id, _, _ = self._setup_trade(client, mock_seller)
        resp = client.post(f"/v1/trades/{trade_id}/execute",
                           json={"input": "test"},
                           headers={"X-API-Key": bkey})
        assert resp.json()["latency_us"] >= 0


# ── Callback failure scenarios ──────────────────────────


class TestCallbackFailure:
    """Seller failures → trade fails, buyer protected by escrow."""

    def _setup_trade(self, client, mock_seller, seller_callback_url=None):
        sid, skey = _register(client)
        bid, bkey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        _fund(bid, 1000)
        url = seller_callback_url or mock_seller
        client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": url,
        }, headers={"X-API-Key": skey})
        trade = client.post("/v1/match", json={"capability_hash": cap},
                            headers={"X-API-Key": bkey}).json()
        return bkey, trade["trade_id"], bid, sid

    def test_seller_500_fails_trade(self, client, mock_seller):
        MockSellerHandler.response_status = 500
        bkey, trade_id, _, _ = self._setup_trade(client, mock_seller)
        resp = client.post(f"/v1/trades/{trade_id}/execute",
                           json={"input": "test"},
                           headers={"X-API-Key": bkey})
        assert resp.json()["status"] == "failed"
        assert resp.json()["reason"] == "callback_failed"

    def test_seller_failure_refunds_buyer(self, client, mock_seller):
        """Buyer's CU balance restored after seller failure."""
        MockSellerHandler.response_status = 500
        bkey, trade_id, bid, _ = self._setup_trade(client, mock_seller)
        from db import get_connection
        # Balance after match (price_cu was escrowed)
        conn = get_connection()
        before = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (bid,)).fetchone()["cu_balance"]
        conn.close()
        resp = client.post(f"/v1/trades/{trade_id}/execute",
                           json={"input": "test"},
                           headers={"X-API-Key": bkey})
        assert resp.json()["status"] == "failed"
        conn = get_connection()
        after = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (bid,)).fetchone()["cu_balance"]
        conn.close()
        # Buyer should get the escrowed amount back
        assert after > before

    def test_seller_failure_escrow_refunded(self, client, mock_seller):
        MockSellerHandler.response_status = 500
        bkey, trade_id, _, _ = self._setup_trade(client, mock_seller)
        client.post(f"/v1/trades/{trade_id}/execute",
                    json={"input": "test"},
                    headers={"X-API-Key": bkey})
        from db import get_connection
        conn = get_connection()
        row = conn.execute("SELECT status FROM escrow WHERE trade_id = ?", (trade_id,)).fetchone()
        conn.close()
        assert row["status"] == "refunded"

    def test_seller_failure_bond_slashed(self, client, mock_seller):
        MockSellerHandler.response_status = 500
        bkey, trade_id, _, sid = self._setup_trade(client, mock_seller)
        from db import get_connection
        conn = get_connection()
        stake_before = conn.execute("SELECT cu_staked FROM sellers WHERE agent_pubkey = ?", (sid,)).fetchone()["cu_staked"]
        conn.close()
        client.post(f"/v1/trades/{trade_id}/execute",
                    json={"input": "test"},
                    headers={"X-API-Key": bkey})
        conn = get_connection()
        stake_after = conn.execute("SELECT cu_staked FROM sellers WHERE agent_pubkey = ?", (sid,)).fetchone()["cu_staked"]
        conn.close()
        assert stake_after < stake_before  # Bond was slashed


# ── Legacy simulated execution ──────────────────────────


class TestLegacyExecution:
    """Sellers without callback_url still use simulated execution."""

    def test_simulated_execution_still_works(self, client):
        """No callback_url → simulated output."""
        sid, skey = _register(client)
        bid, bkey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        _fund(bid, 1000)
        # Register seller WITHOUT callback_url
        client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
        }, headers={"X-API-Key": skey})
        trade = client.post("/v1/match", json={"capability_hash": cap},
                            headers={"X-API-Key": bkey}).json()
        resp = client.post(f"/v1/trades/{trade['trade_id']}/execute",
                           json={"input": "hello world"},
                           headers={"X-API-Key": bkey})
        assert resp.json()["status"] == "executed"
        assert resp.json()["output"] == "executed:hello world"

    def test_null_callback_url_in_db(self, client):
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
        }, headers={"X-API-Key": skey})
        from db import get_connection
        conn = get_connection()
        row = conn.execute("SELECT callback_url FROM sellers WHERE agent_pubkey = ?", (sid,)).fetchone()
        conn.close()
        assert row["callback_url"] is None


# ── Concurrent execution tests ──────────────────────────


class TestConcurrentCallbacks:
    """Multiple trades to same seller."""

    def test_active_calls_tracked_with_real_callback(self, client, mock_seller):
        MockSellerHandler.response_body = {"output": "ok"}
        sid, skey = _register(client)
        cap = _setup_schema(client, skey)
        _fund(sid, 1000)
        client.post("/v1/sellers/register", json={
            "capability_hash": cap, "price_cu": 10.0, "capacity": 5,
            "callback_url": mock_seller,
        }, headers={"X-API-Key": skey})

        # Execute multiple trades
        for _ in range(3):
            bid, bkey = _register(client)
            _fund(bid, 1000)
            trade = client.post("/v1/match", json={"capability_hash": cap},
                                headers={"X-API-Key": bkey}).json()
            resp = client.post(f"/v1/trades/{trade['trade_id']}/execute",
                               json={"input": "test"},
                               headers={"X-API-Key": bkey})
            assert resp.json()["status"] == "executed"

        assert MockSellerHandler.call_count == 3
