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
    pack_error,
)
import db
import matching


def _tcp_payload(api_key: str, body: dict) -> bytes:
    """Build TCP payload: [api_key_len:2][api_key][json_body]."""
    key_bytes = api_key.encode()
    return struct.pack('!H', len(key_bytes)) + key_bytes + json.dumps(body).encode()


@pytest.fixture
def tcp_server(tmp_path, monkeypatch):
    """Start TCP server on a random port, yield (host, port), shutdown after."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("BOTMARKET_DB", db_path)
    monkeypatch.setattr(db, "DB_PATH", db_path)
    matching._seller_tables.clear()
    db.init_db(db_path)

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
    assert b"invalid api key" in resp


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
