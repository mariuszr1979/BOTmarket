# test_tcp.py — Binary TCP server tests
import sys
import os
import asyncio
import json
import struct
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wire import (
    HEADER_SIZE, unpack_header, pack_message,
    MSG_REGISTER_AGENT, MSG_REGISTER_SCHEMA, MSG_REGISTER_SELLER,
    MSG_MATCH_REQUEST, MSG_MATCH_RESPONSE, MSG_EXECUTE,
    MSG_EXECUTE_RESPONSE, MSG_QUERY_EVENTS, MSG_EVENTS_RESPONSE, MSG_ERROR,
    MSG_REGISTER_AGENT_V2, MSG_MATCH_REQUEST_V2, MSG_EXECUTE_V2,
    pack_error,
    pack_match_request_v2, pack_execute_v2,
)
import db
import matching
from identity import generate_keypair, sign_request


def _tcp_payload(api_key: str, body: dict) -> bytes:
    """Build TCP payload: [api_key_len:2][api_key][json_body]."""
    key_bytes = api_key.encode()
    return struct.pack('!H', len(key_bytes)) + key_bytes + json.dumps(body).encode()


@pytest.fixture
def tcp_server(db_setup):
    """Start TCP server on a random port, yield (host, port), shutdown after."""
    from tcp_server import handle_client

    loop = asyncio.new_event_loop()
    server = loop.run_until_complete(
        asyncio.start_server(handle_client, "127.0.0.1", 0)
    )
    port = server.sockets[0].getsockname()[1]

    yield ("127.0.0.1", port, loop)

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()


async def _send_recv(host, port, msg_type, payload):
    """Send a binary message, read the response."""
    reader, writer = await asyncio.open_connection(host, port)
    msg = pack_message(msg_type, payload)
    writer.write(msg)
    await writer.drain()

    header = await reader.readexactly(HEADER_SIZE)
    rt, length = unpack_header(header)
    resp_payload = await reader.readexactly(length)

    writer.close()
    await writer.wait_closed()
    return rt, resp_payload


def _run(loop, coro):
    return loop.run_until_complete(coro)


def _seed_cu(agent_id, amount):
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = ? WHERE pubkey = ?", (amount, agent_id))
    conn.commit()
    conn.close()


# ── Tests ────────────────────────────────────


def test_tcp_register_agent(tcp_server):
    """Register agent via TCP → get agent_id and api_key."""
    host, port, loop = tcp_server
    rt, payload = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    assert rt == MSG_REGISTER_AGENT
    data = json.loads(payload)
    assert "agent_id" in data
    assert "api_key" in data
    assert len(data["api_key"]) == 64


def test_tcp_register_schema(tcp_server):
    """Register schema via TCP → get capability_hash."""
    host, port, loop = tcp_server
    _, agent_payload = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    agent = json.loads(agent_payload)
    api_key = agent["api_key"]

    body = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    payload = _tcp_payload(api_key, body)
    rt, resp = _run(loop, _send_recv(host, port, MSG_REGISTER_SCHEMA, payload))
    assert rt == MSG_REGISTER_SCHEMA
    data = json.loads(resp)
    assert "capability_hash" in data
    assert len(data["capability_hash"]) == 64


def test_tcp_register_seller(tcp_server):
    """Register seller via TCP."""
    host, port, loop = tcp_server
    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    agent = json.loads(ap)

    schema_body = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    _, sp = _run(loop, _send_recv(host, port, MSG_REGISTER_SCHEMA, _tcp_payload(agent["api_key"], schema_body)))
    cap_hash = json.loads(sp)["capability_hash"]

    seller_body = {"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 5}
    _seed_cu(agent["agent_id"], 20.0)
    rt, resp = _run(loop, _send_recv(host, port, MSG_REGISTER_SELLER, _tcp_payload(agent["api_key"], seller_body)))
    assert rt == MSG_REGISTER_SELLER
    data = json.loads(resp)
    assert data["status"] == "registered"


def test_tcp_match_request(tcp_server):
    """Match via TCP → get trade_id."""
    host, port, loop = tcp_server

    # Setup seller
    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    seller = json.loads(ap)
    schema_body = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    _, sp = _run(loop, _send_recv(host, port, MSG_REGISTER_SCHEMA, _tcp_payload(seller["api_key"], schema_body)))
    cap_hash = json.loads(sp)["capability_hash"]
    seller_body = {"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 5}
    _seed_cu(seller["agent_id"], 20.0)
    _run(loop, _send_recv(host, port, MSG_REGISTER_SELLER, _tcp_payload(seller["api_key"], seller_body)))

    # Setup buyer and fund
    _, bp = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    buyer = json.loads(bp)
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = 100.0 WHERE pubkey = ?", (buyer["agent_id"],))
    conn.commit()
    conn.close()

    # Match
    match_body = {"capability_hash": cap_hash}
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST, _tcp_payload(buyer["api_key"], match_body)))
    assert rt == MSG_MATCH_RESPONSE
    data = json.loads(resp)
    assert data["status"] == "matched"
    assert "trade_id" in data
    assert data["price_cu"] == 20.0


def test_tcp_full_lifecycle(tcp_server):
    """Full lifecycle: register → schema → seller → match → execute."""
    host, port, loop = tcp_server

    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    seller = json.loads(ap)
    _, bp = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    buyer = json.loads(bp)

    schema_body = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    _, sp = _run(loop, _send_recv(host, port, MSG_REGISTER_SCHEMA, _tcp_payload(seller["api_key"], schema_body)))
    cap_hash = json.loads(sp)["capability_hash"]

    seller_body = {"capability_hash": cap_hash, "price_cu": 20.0, "capacity": 5}
    _seed_cu(seller["agent_id"], 20.0)
    _run(loop, _send_recv(host, port, MSG_REGISTER_SELLER, _tcp_payload(seller["api_key"], seller_body)))

    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = 100.0 WHERE pubkey = ?", (buyer["agent_id"],))
    conn.commit()
    conn.close()

    match_body = {"capability_hash": cap_hash}
    _, mr = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST, _tcp_payload(buyer["api_key"], match_body)))
    match_data = json.loads(mr)
    assert match_data["status"] == "matched"
    trade_id = match_data["trade_id"]

    exec_body = {"trade_id": trade_id, "input": "hello"}
    _, er = _run(loop, _send_recv(host, port, MSG_EXECUTE, _tcp_payload(buyer["api_key"], exec_body)))
    exec_data = json.loads(er)
    assert exec_data["status"] == "executed"
    assert exec_data["output"] == "executed:hello"


def test_tcp_invalid_msg_type(tcp_server):
    """Unknown msg_type → MSG_ERROR response."""
    host, port, loop = tcp_server
    rt, resp = _run(loop, _send_recv(host, port, 0xFE, b"garbage"))
    assert rt == MSG_ERROR
    assert b"unknown message type" in resp


def test_tcp_invalid_api_key(tcp_server):
    """Bad API key → error response."""
    host, port, loop = tcp_server
    body = {"capability_hash": "abc", "max_price_cu": 10}
    payload = _tcp_payload("bad_key_here", body)
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST, payload))
    assert rt == MSG_ERROR
    assert b"invalid credentials" in resp


def test_tcp_response_valid_binary(tcp_server):
    """Response has correct header: msg_type + payload_length match actual data."""
    host, port, loop = tcp_server
    rt, payload = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    assert rt == MSG_REGISTER_AGENT
    data = json.loads(payload)
    assert isinstance(data, dict)


def test_tcp_multiple_messages_one_connection(tcp_server):
    """Send multiple messages on a single persistent connection."""
    host, port, loop = tcp_server

    async def multi():
        reader, writer = await asyncio.open_connection(host, port)

        writer.write(pack_message(MSG_REGISTER_AGENT, b""))
        await writer.drain()
        h1 = await reader.readexactly(HEADER_SIZE)
        _, l1 = unpack_header(h1)
        p1 = await reader.readexactly(l1)
        a1 = json.loads(p1)

        writer.write(pack_message(MSG_REGISTER_AGENT, b""))
        await writer.drain()
        h2 = await reader.readexactly(HEADER_SIZE)
        _, l2 = unpack_header(h2)
        p2 = await reader.readexactly(l2)
        a2 = json.loads(p2)

        writer.close()
        await writer.wait_closed()
        return a1, a2

    a1, a2 = _run(loop, multi())
    assert a1["agent_id"] != a2["agent_id"]
    assert a1["api_key"] != a2["api_key"]


def test_tcp_concurrent_connections(tcp_server):
    """10 concurrent TCP connections all handled correctly."""
    host, port, loop = tcp_server

    async def register_one():
        reader, writer = await asyncio.open_connection(host, port)
        writer.write(pack_message(MSG_REGISTER_AGENT, b""))
        await writer.drain()
        h = await reader.readexactly(HEADER_SIZE)
        _, l = unpack_header(h)
        p = await reader.readexactly(l)
        writer.close()
        await writer.wait_closed()
        return json.loads(p)

    async def run_all():
        return await asyncio.gather(*[register_one() for _ in range(10)])

    results = _run(loop, run_all())
    ids = [r["agent_id"] for r in results]
    assert len(set(ids)) == 10


def test_tcp_query_events(tcp_server):
    """Query events via TCP."""
    host, port, loop = tcp_server
    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    agent = json.loads(ap)

    body = {"agent_id": agent["agent_id"]}
    rt, resp = _run(loop, _send_recv(host, port, MSG_QUERY_EVENTS, _tcp_payload(agent["api_key"], body)))
    assert rt == MSG_EVENTS_RESPONSE
    data = json.loads(resp)
    assert data["agent_id"] == agent["agent_id"]
    assert len(data["events"]) >= 1


def test_tcp_no_match(tcp_server):
    """Match for non-existent capability → no_match."""
    host, port, loop = tcp_server
    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    agent = json.loads(ap)
    conn = db.get_connection()
    conn.execute("UPDATE agents SET cu_balance = 100.0 WHERE pubkey = ?", (agent["agent_id"],))
    conn.commit()
    conn.close()

    body = {"capability_hash": "nonexistent_hash_000000000000000"}
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST, _tcp_payload(agent["api_key"], body)))
    assert rt == MSG_MATCH_RESPONSE
    data = json.loads(resp)
    assert data["status"] == "no_match"


# ── V2 authenticated tests ───────────────────────────

def _v2_register(loop, host, port, pubkey_hex):
    """Register a v2 agent (Ed25519 pubkey). Returns response dict."""
    payload = bytes.fromhex(pubkey_hex)
    rt, resp = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT_V2, payload))
    return rt, json.loads(resp)


def _v2_match_payload(pubkey_hex, privkey_hex, cap_hash_hex, max_price_cu=0):
    """Build signed v2 match payload (everything after the 5-byte wire header)."""
    cap_hash_bytes = bytes.fromhex(cap_hash_hex)
    inner = struct.pack('!32sQ', cap_hash_bytes, max_price_cu)
    sig_hex, ts_ns = sign_request(inner, privkey_hex)
    return pack_match_request_v2(pubkey_hex, sig_hex, ts_ns, cap_hash_bytes, max_price_cu)[HEADER_SIZE:]


def _v2_execute_payload(pubkey_hex, privkey_hex, trade_id_str, input_data: bytes):
    """Build signed v2 execute payload (everything after the 5-byte wire header)."""
    import uuid
    trade_id_bytes = uuid.UUID(trade_id_str).bytes
    padded = trade_id_bytes.ljust(32, b'\x00')
    inner = padded + input_data
    sig_hex, ts_ns = sign_request(inner, privkey_hex)
    return pack_execute_v2(pubkey_hex, sig_hex, ts_ns, trade_id_bytes, input_data)[HEADER_SIZE:]


def test_tcp_v2_register_agent(tcp_server):
    """V2 agent registration by Ed25519 pubkey → status registered."""
    host, port, loop = tcp_server
    privkey, pubkey = generate_keypair()
    rt, data = _v2_register(loop, host, port, pubkey)
    assert rt == MSG_REGISTER_AGENT_V2
    assert data["status"] == "registered"
    assert data["pubkey"] == pubkey


def test_tcp_v2_register_idempotent(tcp_server):
    """V2 agent re-registration is idempotent (INSERT OR IGNORE)."""
    host, port, loop = tcp_server
    privkey, pubkey = generate_keypair()
    _v2_register(loop, host, port, pubkey)
    rt, data = _v2_register(loop, host, port, pubkey)
    assert rt == MSG_REGISTER_AGENT_V2
    assert data["status"] == "registered"


def test_tcp_v2_match_signed(tcp_server):
    """V2 buyer sends signed match request → matched."""
    host, port, loop = tcp_server

    # Register v1 seller
    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    seller = json.loads(ap)
    schema_body = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    _, sp = _run(loop, _send_recv(host, port, MSG_REGISTER_SCHEMA, _tcp_payload(seller["api_key"], schema_body)))
    cap_hash = json.loads(sp)["capability_hash"]
    _seed_cu(seller["agent_id"], 25.0)
    seller_body = {"capability_hash": cap_hash, "price_cu": 25.0, "capacity": 5}
    _run(loop, _send_recv(host, port, MSG_REGISTER_SELLER, _tcp_payload(seller["api_key"], seller_body)))

    # Register v2 buyer and fund
    privkey, pubkey = generate_keypair()
    _v2_register(loop, host, port, pubkey)
    _seed_cu(pubkey, 100.0)

    # Signed match request
    payload = _v2_match_payload(pubkey, privkey, cap_hash)
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST_V2, payload))
    # Response is binary: pack_match_response layout
    assert rt == MSG_MATCH_RESPONSE
    # status=1 (matched) is in byte 73 (last of the 73-byte payload)
    assert resp[-1] == 1


def test_tcp_v2_execute_signed(tcp_server):
    """V2 buyer: register → match → execute with signed requests → executed."""
    host, port, loop = tcp_server

    # Setup v1 seller
    _, ap = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    seller = json.loads(ap)
    schema_body = {"input_schema": {"type": "string"}, "output_schema": {"type": "string"}}
    _, sp = _run(loop, _send_recv(host, port, MSG_REGISTER_SCHEMA, _tcp_payload(seller["api_key"], schema_body)))
    cap_hash = json.loads(sp)["capability_hash"]
    _seed_cu(seller["agent_id"], 30.0)
    _run(loop, _send_recv(host, port, MSG_REGISTER_SELLER, _tcp_payload(
        seller["api_key"], {"capability_hash": cap_hash, "price_cu": 30.0, "capacity": 5}
    )))

    # Register v2 buyer and fund
    privkey, pubkey = generate_keypair()
    _v2_register(loop, host, port, pubkey)
    _seed_cu(pubkey, 100.0)

    # Match
    match_payload = _v2_match_payload(pubkey, privkey, cap_hash)
    rt, match_resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST_V2, match_payload))
    assert rt == MSG_MATCH_RESPONSE
    assert match_resp[-1] == 1  # status matched
    # Extract trade_id (first 32 bytes = UUID padded)
    import uuid
    trade_id = str(uuid.UUID(bytes=match_resp[:16]))

    # Execute
    execute_payload = _v2_execute_payload(pubkey, privkey, trade_id, b"hello v2")
    rt, exec_resp = _run(loop, _send_recv(host, port, MSG_EXECUTE_V2, execute_payload))
    assert rt == MSG_EXECUTE_RESPONSE
    # status byte is at position 40; output follows at 41+
    assert exec_resp[40] == 1  # status executed
    assert b"executed:hello v2" in exec_resp[41:]


def test_tcp_v2_invalid_signature(tcp_server):
    """V2 match with tampered signature → MSG_ERROR."""
    host, port, loop = tcp_server

    privkey, pubkey = generate_keypair()
    _v2_register(loop, host, port, pubkey)
    _seed_cu(pubkey, 100.0)

    # Build a valid-looking payload but forge the signature
    cap_hash_hex = "a" * 64  # fake hash
    fake_sig = "b" * 128     # wrong signature (64 bogus bytes)
    import time as _time
    ts_ns = _time.time_ns()
    cap_hash_bytes = bytes.fromhex(cap_hash_hex)
    payload = pack_match_request_v2(pubkey, fake_sig, ts_ns, cap_hash_bytes, 0)[HEADER_SIZE:]
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST_V2, payload))
    assert rt == MSG_ERROR


def test_tcp_v2_expired_timestamp(tcp_server):
    """V2 match with timestamp >30s old → MSG_ERROR."""
    host, port, loop = tcp_server

    privkey, pubkey = generate_keypair()
    _v2_register(loop, host, port, pubkey)
    _seed_cu(pubkey, 100.0)

    cap_hash_hex = "a" * 64
    cap_hash_bytes = bytes.fromhex(cap_hash_hex)
    inner = struct.pack('!32sQ', cap_hash_bytes, 0)
    # Sign with a timestamp 60 seconds in the past
    old_ts_ns = (__import__('time').time_ns()) - 60_000_000_000
    from identity import sign
    from identity import canonical_bytes
    message = str(old_ts_ns).encode() + b":" + canonical_bytes(inner)
    sig_hex = sign(message, privkey)
    payload = pack_match_request_v2(pubkey, sig_hex, old_ts_ns, cap_hash_bytes, 0)[HEADER_SIZE:]
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST_V2, payload))
    assert rt == MSG_ERROR


def test_tcp_v2_unregistered_pubkey(tcp_server):
    """V2 request from unregistered pubkey → MSG_ERROR."""
    host, port, loop = tcp_server

    privkey, pubkey = generate_keypair()
    # Do NOT register — try to match directly
    cap_hash_hex = "a" * 64
    payload = _v2_match_payload(pubkey, privkey, cap_hash_hex)
    rt, resp = _run(loop, _send_recv(host, port, MSG_MATCH_REQUEST_V2, payload))
    assert rt == MSG_ERROR


def test_tcp_v1_v2_backward_compat(tcp_server):
    """V1 clients still work unaffected alongside v2 handlers."""
    host, port, loop = tcp_server
    # V1 register still works
    rt, payload = _run(loop, _send_recv(host, port, MSG_REGISTER_AGENT, b""))
    assert rt == MSG_REGISTER_AGENT
    data = json.loads(payload)
    assert "agent_id" in data
    assert "api_key" in data
