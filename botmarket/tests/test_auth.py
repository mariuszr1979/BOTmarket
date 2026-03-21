# tests/test_auth.py — Step 1: Signature-Based Authentication tests
import asyncio
import json
import struct
import time

import pytest
from starlette.testclient import TestClient

from identity import generate_keypair, sign_request, canonical_bytes
from main import app


SAMPLE_INPUT = {"type": "object", "properties": {"text": {"type": "string"}}}
SAMPLE_OUTPUT = {"type": "object", "properties": {"result": {"type": "string"}}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BOTMARKET_DB", str(tmp_path / "test.db"))
    import db
    import matching
    db.DB_PATH = str(tmp_path / "test.db")
    db.init_db().close()
    matching._seller_tables.clear()
    with TestClient(app) as c:
        yield c


def _register_ed25519(client):
    """Register an Ed25519 agent. Returns (private_key_hex, public_key_hex)."""
    priv, pub = generate_keypair()
    resp = client.post("/v1/agents/register/v2", json={"public_key": pub})
    assert resp.status_code == 201
    return priv, pub


def _ed25519_headers(body, priv, pub, timestamp_ns=None):
    """Build Ed25519 auth headers for a request body (dict, str, or bytes)."""
    sig, ts = sign_request(body, priv, timestamp_ns)
    return {
        "X-Public-Key": pub,
        "X-Signature": sig,
        "X-Timestamp": str(ts),
    }


def _register_legacy(client):
    """Register a legacy API key agent. Returns (agent_id, api_key)."""
    resp = client.post("/v1/agents/register")
    assert resp.status_code == 201
    data = resp.json()
    return data["agent_id"], data["api_key"]


# ── Ed25519 auth on all endpoints ──────────────────────


class TestEd25519HttpAuth:
    """Ed25519 signature auth works on all authenticated HTTP endpoints."""

    def test_schema_register_ed25519(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(body, priv, pub)
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 201
        assert "capability_hash" in resp.json()

    def test_seller_register_ed25519(self, client):
        priv, pub = _register_ed25519(client)
        # Register schema first
        schema_body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(schema_body, priv, pub)
        cap = client.post("/v1/schemas/register", json=schema_body, headers=headers).json()["capability_hash"]
        # Fund agent
        from db import get_connection
        conn = get_connection()
        conn.execute("UPDATE agents SET cu_balance = 100 WHERE pubkey = ?", (pub,))
        conn.commit()
        conn.close()
        # Register seller
        seller_body = {"capability_hash": cap, "price_cu": 10.0, "capacity": 5}
        headers = _ed25519_headers(seller_body, priv, pub)
        resp = client.post("/v1/sellers/register", json=seller_body, headers=headers)
        assert resp.status_code == 201

    def test_match_ed25519(self, client):
        priv_s, pub_s = _register_ed25519(client)
        priv_b, pub_b = _register_ed25519(client)
        # Schema
        schema_body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        cap = client.post("/v1/schemas/register", json=schema_body,
                          headers=_ed25519_headers(schema_body, priv_s, pub_s)).json()["capability_hash"]
        # Fund both
        from db import get_connection
        conn = get_connection()
        conn.execute("UPDATE agents SET cu_balance = 1000 WHERE pubkey IN (?, ?)", (pub_s, pub_b))
        conn.commit()
        conn.close()
        # Seller
        seller_body = {"capability_hash": cap, "price_cu": 10.0, "capacity": 5}
        client.post("/v1/sellers/register", json=seller_body,
                    headers=_ed25519_headers(seller_body, priv_s, pub_s))
        # Match
        match_body = {"capability_hash": cap}
        headers = _ed25519_headers(match_body, priv_b, pub_b)
        resp = client.post("/v1/match", json=match_body, headers=headers)
        assert resp.json()["status"] == "matched"

    def test_execute_ed25519(self, client):
        priv_s, pub_s = _register_ed25519(client)
        priv_b, pub_b = _register_ed25519(client)
        schema_body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        cap = client.post("/v1/schemas/register", json=schema_body,
                          headers=_ed25519_headers(schema_body, priv_s, pub_s)).json()["capability_hash"]
        from db import get_connection
        conn = get_connection()
        conn.execute("UPDATE agents SET cu_balance = 1000 WHERE pubkey IN (?, ?)", (pub_s, pub_b))
        conn.commit()
        conn.close()
        seller_body = {"capability_hash": cap, "price_cu": 10.0, "capacity": 5}
        client.post("/v1/sellers/register", json=seller_body,
                    headers=_ed25519_headers(seller_body, priv_s, pub_s))
        match_body = {"capability_hash": cap}
        trade_id = client.post("/v1/match", json=match_body,
                               headers=_ed25519_headers(match_body, priv_b, pub_b)).json()["trade_id"]
        exec_body = {"input": "hello"}
        headers = _ed25519_headers(exec_body, priv_b, pub_b)
        resp = client.post(f"/v1/trades/{trade_id}/execute", json=exec_body, headers=headers)
        assert resp.json()["status"] == "executed"

    def test_settle_ed25519(self, client):
        priv_s, pub_s = _register_ed25519(client)
        priv_b, pub_b = _register_ed25519(client)
        schema_body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        cap = client.post("/v1/schemas/register", json=schema_body,
                          headers=_ed25519_headers(schema_body, priv_s, pub_s)).json()["capability_hash"]
        from db import get_connection
        conn = get_connection()
        conn.execute("UPDATE agents SET cu_balance = 1000 WHERE pubkey IN (?, ?)", (pub_s, pub_b))
        conn.commit()
        conn.close()
        seller_body = {"capability_hash": cap, "price_cu": 10.0, "capacity": 5}
        client.post("/v1/sellers/register", json=seller_body,
                    headers=_ed25519_headers(seller_body, priv_s, pub_s))
        match_body = {"capability_hash": cap}
        trade_id = client.post("/v1/match", json=match_body,
                               headers=_ed25519_headers(match_body, priv_b, pub_b)).json()["trade_id"]
        exec_body = {"input": "hello"}
        client.post(f"/v1/trades/{trade_id}/execute", json=exec_body,
                    headers=_ed25519_headers(exec_body, priv_b, pub_b))
        # Settle (no body for POST)
        headers = _ed25519_headers(b"", priv_b, pub_b)
        resp = client.post(f"/v1/trades/{trade_id}/settle", headers=headers)
        assert resp.json()["status"] == "completed"

    def test_events_ed25519(self, client):
        priv, pub = _register_ed25519(client)
        # GET has no body
        headers = _ed25519_headers(b"", priv, pub)
        resp = client.get(f"/v1/events/{pub}", headers=headers)
        assert resp.status_code == 200
        assert "events" in resp.json()


# ── Dual-mode: both auth methods work ──────────────────


class TestDualModeAuth:
    """Both Ed25519 and API key auth work on the same endpoints."""

    def test_legacy_api_key_still_works(self, client):
        _, api_key = _register_legacy(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        resp = client.post("/v1/schemas/register", json=body, headers={"X-API-Key": api_key})
        assert resp.status_code == 201

    def test_ed25519_takes_priority(self, client):
        """When both Ed25519 and API-key headers are present, Ed25519 wins."""
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(body, priv, pub)
        headers["X-API-Key"] = "garbage_key_that_would_fail"
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 201  # Ed25519 succeeded despite bad API key

    def test_ed25519_agent_has_no_api_key(self, client):
        priv, pub = _register_ed25519(client)
        from db import get_connection
        conn = get_connection()
        row = conn.execute("SELECT api_key FROM agents WHERE pubkey = ?", (pub,)).fetchone()
        conn.close()
        assert row["api_key"] is None


# ── Invalid signature scenarios ─────────────────────────


class TestInvalidSignature:
    """Invalid signatures are properly rejected."""

    def test_invalid_signature_rejected(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(body, priv, pub)
        headers["X-Signature"] = "ff" * 64  # fake 64-byte signature
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 401

    def test_tampered_body_rejected(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(body, priv, pub)
        # Sign body A, send body B
        tampered = {"input_schema": {"type": "number"}, "output_schema": SAMPLE_OUTPUT}
        resp = client.post("/v1/schemas/register", json=tampered, headers=headers)
        assert resp.status_code == 401

    def test_unknown_pubkey_rejected(self, client):
        priv, pub = generate_keypair()  # Not registered
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(body, priv, pub)
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 401

    def test_missing_all_auth_headers(self, client):
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        resp = client.post("/v1/schemas/register", json=body)
        assert resp.status_code == 401
        assert "missing authentication" in resp.json()["detail"]

    def test_partial_ed25519_headers_falls_to_missing(self, client):
        """Only pubkey header, no signature/timestamp → falls through to missing auth."""
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        resp = client.post("/v1/schemas/register", json=body,
                           headers={"X-Public-Key": pub})
        assert resp.status_code == 401


# ── Replay protection ──────────────────────────────────


class TestReplayProtection:
    """Timestamp-based replay protection."""

    def test_valid_timestamp_accepted(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        headers = _ed25519_headers(body, priv, pub)  # uses current time
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 201

    def test_expired_timestamp_rejected(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        old_ts = time.time_ns() - 31_000_000_000  # 31 seconds ago
        headers = _ed25519_headers(body, priv, pub, timestamp_ns=old_ts)
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 401
        assert "timestamp_expired" in resp.json()["detail"]

    def test_future_timestamp_rejected(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        future_ts = time.time_ns() + 31_000_000_000  # 31 seconds in future
        headers = _ed25519_headers(body, priv, pub, timestamp_ns=future_ts)
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 401

    def test_within_window_accepted(self, client):
        priv, pub = _register_ed25519(client)
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        recent_ts = time.time_ns() - 10_000_000_000  # 10 seconds ago (within 30s)
        headers = _ed25519_headers(body, priv, pub, timestamp_ns=recent_ts)
        resp = client.post("/v1/schemas/register", json=body, headers=headers)
        assert resp.status_code == 201


# ── Bulk signature tests ───────────────────────────────


class TestBulkSignature:
    """Stress tests for signature verification."""

    def test_1000_valid_signatures(self, client):
        """1000 requests with valid signatures → all pass."""
        priv, pub = _register_ed25519(client)
        for i in range(1000):
            body = {"input_schema": {"type": "object", "id": i}, "output_schema": SAMPLE_OUTPUT}
            headers = _ed25519_headers(body, priv, pub)
            resp = client.post("/v1/schemas/register", json=body, headers=headers)
            assert resp.status_code == 201, f"Failed at iteration {i}"

    def test_1000_tampered_bodies(self, client):
        """1000 requests with tampered bodies → all fail."""
        priv, pub = _register_ed25519(client)
        for i in range(1000):
            body = {"input_schema": {"type": "object", "id": i}, "output_schema": SAMPLE_OUTPUT}
            headers = _ed25519_headers(body, priv, pub)
            tampered = {"input_schema": {"type": "object", "id": i + 1}, "output_schema": SAMPLE_OUTPUT}
            resp = client.post("/v1/schemas/register", json=tampered, headers=headers)
            assert resp.status_code == 401, f"Tamper not caught at iteration {i}"


# ── TCP Ed25519 auth tests ─────────────────────────────


class TestTcpEd25519:
    """Ed25519 authentication over TCP binary protocol."""

    @pytest.fixture
    def tcp_server(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BOTMARKET_DB", str(tmp_path / "test.db"))
        import asyncio
        import db
        import matching
        from tcp_server import handle_client

        db.DB_PATH = str(tmp_path / "test.db")
        conn = db.init_db()
        matching.rebuild_seller_tables(conn)
        conn.close()
        matching._seller_tables.clear()

        loop = asyncio.new_event_loop()
        server = loop.run_until_complete(
            asyncio.start_server(handle_client, "127.0.0.1", 0)
        )
        port = server.sockets[0].getsockname()[1]
        yield "127.0.0.1", port, loop
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()

    def _tcp_ed25519_payload(self, priv_hex, pub_hex, body_dict):
        """Build TCP payload with Ed25519 auth.
        Format: [0x0000][32B pubkey][64B sig][8B timestamp BE][json body]"""
        body_bytes = json.dumps(body_dict, sort_keys=True, separators=(",", ":")).encode()
        ts_ns = time.time_ns()
        # Sign: timestamp:body
        from identity import sign
        message = str(ts_ns).encode("utf-8") + b":" + body_bytes
        sig_hex = sign(message, priv_hex)

        return (
            struct.pack('!H', 0) +           # key_len = 0 → Ed25519 mode
            bytes.fromhex(pub_hex) +          # 32 bytes pubkey
            bytes.fromhex(sig_hex) +          # 64 bytes signature
            struct.pack('!Q', ts_ns) +        # 8 bytes timestamp
            body_bytes                        # JSON body
        )

    def _tcp_apikey_payload(self, api_key, body_dict):
        """Build TCP payload with API key auth (legacy)."""
        key_bytes = api_key.encode()
        body_bytes = json.dumps(body_dict).encode()
        return struct.pack('!H', len(key_bytes)) + key_bytes + body_bytes

    async def _send_recv(self, host, port, msg_type, payload):
        reader, writer = await asyncio.open_connection(host, port)
        from wire import pack_message, unpack_header, HEADER_SIZE
        writer.write(pack_message(msg_type, payload))
        await writer.drain()
        header = await asyncio.wait_for(reader.readexactly(HEADER_SIZE), timeout=5)
        rt, plen = unpack_header(header)
        data = await asyncio.wait_for(reader.readexactly(plen), timeout=5)
        writer.close()
        await writer.wait_closed()
        return rt, data

    def _run(self, loop, coro):
        return loop.run_until_complete(coro)

    def test_tcp_ed25519_register_schema(self, tcp_server):
        """Ed25519 auth works for TCP schema registration."""
        import asyncio
        from wire import MSG_REGISTER_AGENT, MSG_REGISTER_SCHEMA
        host, port, loop = tcp_server

        # Register agent via TCP (legacy)
        rt, resp = self._run(loop, self._send_recv(host, port, MSG_REGISTER_AGENT, b""))
        agent = json.loads(resp)

        # Now register via v2 (direct DB insert since TCP register_agent gives API key)
        priv, pub = generate_keypair()
        from db import get_connection
        conn = get_connection()
        conn.execute(
            "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, NULL, 0.0, ?)",
            (pub, time.time_ns()),
        )
        conn.commit()
        conn.close()

        # Register schema with Ed25519
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        payload = self._tcp_ed25519_payload(priv, pub, body)
        rt, resp = self._run(loop, self._send_recv(host, port, MSG_REGISTER_SCHEMA, payload))
        assert rt == MSG_REGISTER_SCHEMA
        data = json.loads(resp)
        assert "capability_hash" in data

    def test_tcp_ed25519_invalid_sig_rejected(self, tcp_server):
        """TCP Ed25519 with tampered payload → error."""
        import asyncio
        from wire import MSG_REGISTER_SCHEMA, MSG_ERROR
        host, port, loop = tcp_server

        priv, pub = generate_keypair()
        from db import get_connection
        conn = get_connection()
        conn.execute(
            "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, NULL, 0.0, ?)",
            (pub, time.time_ns()),
        )
        conn.commit()
        conn.close()

        # Build valid payload then tamper the body bytes
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        payload = bytearray(self._tcp_ed25519_payload(priv, pub, body))
        # Tamper: flip last byte of body
        payload[-1] = (payload[-1] + 1) % 256
        rt, resp = self._run(loop, self._send_recv(host, port, MSG_REGISTER_SCHEMA, bytes(payload)))
        assert rt == MSG_ERROR

    def test_tcp_legacy_apikey_still_works(self, tcp_server):
        """Legacy API key auth still works on TCP after Ed25519 addition."""
        import asyncio
        from wire import MSG_REGISTER_AGENT, MSG_REGISTER_SCHEMA
        host, port, loop = tcp_server

        # Register agent (returns API key)
        rt, resp = self._run(loop, self._send_recv(host, port, MSG_REGISTER_AGENT, b""))
        agent = json.loads(resp)
        api_key = agent["api_key"]

        # Register schema with API key
        body = {"input_schema": SAMPLE_INPUT, "output_schema": SAMPLE_OUTPUT}
        payload = self._tcp_apikey_payload(api_key, body)
        rt, resp = self._run(loop, self._send_recv(host, port, MSG_REGISTER_SCHEMA, payload))
        assert rt == MSG_REGISTER_SCHEMA
        data = json.loads(resp)
        assert "capability_hash" in data
