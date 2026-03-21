import asyncio
import hashlib
import json
import secrets
import struct
import uuid
import time

from wire import (
    HEADER_SIZE, unpack_header, pack_message,
    MSG_REGISTER_AGENT, MSG_REGISTER_SCHEMA, MSG_REGISTER_SELLER,
    MSG_MATCH_REQUEST, MSG_MATCH_RESPONSE, MSG_EXECUTE,
    MSG_EXECUTE_RESPONSE, MSG_QUERY_EVENTS, MSG_EVENTS_RESPONSE, MSG_ERROR,
    MSG_REGISTER_AGENT_V2, MSG_MATCH_REQUEST_V2, MSG_EXECUTE_V2,
    unpack_match_request, pack_match_response,
    unpack_execute, pack_execute_response,
    unpack_query_events, pack_events_response,
    unpack_register_seller, pack_error,
    unpack_v2_auth, unpack_register_agent_v2,
    unpack_match_request_v2_payload, unpack_execute_v2_payload,
)
from db import init_db, get_connection
from events import record_event, query_events
from log import log
from matching import rebuild_seller_tables, add_seller, match_request, increment_active_calls, decrement_active_calls
from verification import verify_trade
from settlement import settle_trade, slash_bond, maybe_set_sla, check_sla_decoherence
from identity import verify_request


def _auth_key(api_key_bytes: bytes) -> str | None:
    """Authenticate by API key bytes. Returns pubkey or None."""
    key = api_key_bytes.rstrip(b'\x00').decode('utf-8', errors='replace')
    conn = get_connection()
    try:
        row = conn.execute("SELECT pubkey FROM agents WHERE api_key = ?", (key,)).fetchone()
    finally:
        conn.close()
    return row["pubkey"] if row else None


def _tcp_authenticate(payload: bytes):
    """Dual-mode TCP auth. Returns (pubkey, body_bytes) or (None, b"").
    Format detection: key_len == 0 → Ed25519, key_len > 0 → API key.
    Ed25519: [0x00 0x00][32B pubkey][64B sig][8B timestamp_ns BE][json body]
    API key: [key_len:2 BE][api_key][json body]"""
    if len(payload) < 2:
        return None, b""
    key_len = struct.unpack('!H', payload[:2])[0]

    if key_len == 0:
        # Ed25519 mode: 2 + 32 + 64 + 8 = 106 bytes header
        if len(payload) < 106:
            return None, b""
        pubkey_hex = payload[2:34].hex()
        sig_hex = payload[34:98].hex()
        ts_ns = struct.unpack('!Q', payload[98:106])[0]
        body_bytes = payload[106:]

        valid, reason = verify_request(sig_hex, body_bytes, pubkey_hex, ts_ns)
        if not valid:
            return None, b""

        conn = get_connection()
        try:
            row = conn.execute("SELECT pubkey FROM agents WHERE pubkey = ?", (pubkey_hex,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None, b""
        return pubkey_hex, body_bytes

    else:
        # API key mode
        api_key = payload[2:2 + key_len].decode()
        body_bytes = payload[2 + key_len:]
        pubkey = _auth_key(api_key.encode())
        return pubkey, body_bytes


def handle_register_agent(payload: bytes) -> bytes:
    pubkey = str(uuid.uuid4())
    api_key = secrets.token_hex(32)
    now_ns = time.time_ns()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, ?, 0.0, ?)",
            (pubkey, api_key, now_ns),
        )
        record_event(conn, "agent_registered", json.dumps({"agent": pubkey}))
        conn.commit()
    finally:
        conn.close()
    resp = json.dumps({"agent_id": pubkey, "api_key": api_key}).encode()
    return pack_message(MSG_REGISTER_AGENT, resp)


def handle_register_schema(payload: bytes) -> bytes:
    agent_pubkey, body_bytes = _tcp_authenticate(payload)
    if not agent_pubkey:
        return pack_error(0x02, b"invalid credentials")
    body = json.loads(body_bytes)

    canonical_input = json.dumps(body["input_schema"], sort_keys=True, separators=(",", ":"))
    canonical_output = json.dumps(body["output_schema"], sort_keys=True, separators=(",", ":"))
    combined = canonical_input + "||" + canonical_output
    capability_hash = hashlib.sha256(combined.encode()).hexdigest()

    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO schemas (capability_hash, input_schema, output_schema, registered_at) VALUES (?, ?, ?, ?)",
            (capability_hash, canonical_input, canonical_output, time.time_ns()),
        )
        record_event(conn, "schema_registered", json.dumps({
            "capability_hash": capability_hash, "agent": agent_pubkey,
        }))
        conn.commit()
    finally:
        conn.close()
    resp = json.dumps({"capability_hash": capability_hash}).encode()
    return pack_message(MSG_REGISTER_SCHEMA, resp)


def handle_register_seller(payload: bytes) -> bytes:
    agent_pubkey, body_bytes = _tcp_authenticate(payload)
    if not agent_pubkey:
        return pack_error(0x02, b"invalid credentials")
    body = json.loads(body_bytes)

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT capability_hash FROM schemas WHERE capability_hash = ?",
            (body["capability_hash"],),
        ).fetchone()
        if row is None:
            return pack_error(0x03, b"capability_hash not found")

        # Stake = price_cu
        stake = body["price_cu"]

        # Refund any existing stake before re-registration (CU invariant)
        old = conn.execute(
            "SELECT cu_staked FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
            (agent_pubkey, body["capability_hash"]),
        ).fetchone()
        old_stake = old["cu_staked"] if old else 0

        agent_row = conn.execute(
            "SELECT cu_balance FROM agents WHERE pubkey = ?", (agent_pubkey,)
        ).fetchone()
        effective_balance = (agent_row["cu_balance"] + old_stake) if agent_row else 0
        if agent_row is None or effective_balance < stake:
            return pack_error(0x04, b"insufficient CU balance for stake")

        conn.execute(
            "UPDATE agents SET cu_balance = cu_balance + ? - ? WHERE pubkey = ?",
            (old_stake, stake, agent_pubkey),
        )

        now_ns = time.time_ns()
        conn.execute(
            "INSERT OR REPLACE INTO sellers "
            "(agent_pubkey, capability_hash, price_cu, latency_bound_us, capacity, active_calls, cu_staked, callback_url, sla_set_at_ns, registered_at_ns) "
            "VALUES (?, ?, ?, 0, ?, 0, ?, ?, NULL, ?)",
            (agent_pubkey, body["capability_hash"], body["price_cu"], body["capacity"], stake, body.get("callback_url"), now_ns),
        )
        record_event(conn, "seller_registered", json.dumps({
            "agent": agent_pubkey,
            "capability_hash": body["capability_hash"],
            "price_cu": body["price_cu"],
            "cu_staked": stake,
        }))
        conn.commit()
    finally:
        conn.close()

    seller = {
        "agent_pubkey": agent_pubkey,
        "capability_hash": body["capability_hash"],
        "price_cu": body["price_cu"],
        "latency_bound_us": 0,
        "capacity": body["capacity"],
        "active_calls": 0,
        "cu_staked": stake,
    }
    add_seller(seller)
    resp = json.dumps({"status": "registered", "capability_hash": body["capability_hash"]}).encode()
    return pack_message(MSG_REGISTER_SELLER, resp)


def handle_match(payload: bytes) -> bytes:
    buyer_pubkey, body_bytes = _tcp_authenticate(payload)
    if not buyer_pubkey:
        return pack_error(0x02, b"invalid credentials")
    body = json.loads(body_bytes)

    seller = match_request(body["capability_hash"], body.get("max_price_cu"), body.get("max_latency_us"))
    if seller is None:
        return pack_message(MSG_MATCH_RESPONSE, json.dumps({"status": "no_match"}).encode())

    conn = get_connection()
    try:
        row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (buyer_pubkey,)).fetchone()
        if row["cu_balance"] < seller["price_cu"]:
            return pack_message(MSG_MATCH_RESPONSE, json.dumps({"status": "insufficient_cu"}).encode())

        trade_id = str(uuid.uuid4())
        now_ns = time.time_ns()
        conn.execute("UPDATE agents SET cu_balance = cu_balance - ? WHERE pubkey = ?", (seller["price_cu"], buyer_pubkey))
        conn.execute(
            "INSERT INTO trades (id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, start_ns, status) VALUES (?, ?, ?, ?, ?, ?, 'matched')",
            (trade_id, buyer_pubkey, seller["agent_pubkey"], body["capability_hash"], seller["price_cu"], now_ns),
        )
        conn.execute(
            "INSERT INTO escrow (trade_id, buyer_pubkey, seller_pubkey, cu_amount, status) VALUES (?, ?, ?, ?, 'held')",
            (trade_id, buyer_pubkey, seller["agent_pubkey"], seller["price_cu"]),
        )
        conn.execute(
            "UPDATE sellers SET active_calls = active_calls + 1 WHERE agent_pubkey = ? AND capability_hash = ?",
            (seller["agent_pubkey"], body["capability_hash"]),
        )
        record_event(conn, "match_made", json.dumps({
            "trade_id": trade_id, "buyer": buyer_pubkey, "seller": seller["agent_pubkey"],
            "capability_hash": body["capability_hash"], "price_cu": seller["price_cu"],
        }))
        conn.commit()
    finally:
        conn.close()

    increment_active_calls(seller["agent_pubkey"], body["capability_hash"])
    resp = json.dumps({
        "trade_id": trade_id, "seller_pubkey": seller["agent_pubkey"],
        "price_cu": seller["price_cu"], "status": "matched",
    }).encode()
    return pack_message(MSG_MATCH_RESPONSE, resp)


def handle_execute(payload: bytes) -> bytes:
    caller_pubkey, body_bytes = _tcp_authenticate(payload)
    if not caller_pubkey:
        return pack_error(0x02, b"invalid credentials")
    body = json.loads(body_bytes)

    trade_id = body["trade_id"]
    conn = get_connection()
    try:
        trade = conn.execute(
            "SELECT buyer_pubkey, seller_pubkey, capability_hash, price_cu, status FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        if trade is None:
            return pack_error(0x04, b"trade not found")
        if trade["buyer_pubkey"] != caller_pubkey:
            return pack_error(0x05, b"not the buyer")
        if trade["status"] != "matched":
            return pack_error(0x06, b"trade not in matched status")

        start_ns = time.time_ns()
        output_data = f"executed:{body['input']}"
        end_ns = time.time_ns()
        latency_us = (end_ns - start_ns) // 1000

        conn.execute(
            "UPDATE trades SET start_ns = ?, end_ns = ?, latency_us = ?, status = 'executed' WHERE id = ?",
            (start_ns, end_ns, latency_us, trade_id),
        )
        conn.execute(
            "UPDATE sellers SET active_calls = MAX(0, active_calls - 1) WHERE agent_pubkey = ? AND capability_hash = ?",
            (trade["seller_pubkey"], trade["capability_hash"]),
        )
        record_event(conn, "trade_executed", json.dumps({
            "trade_id": trade_id, "buyer": caller_pubkey, "seller": trade["seller_pubkey"], "latency_us": latency_us,
        }))
        conn.commit()
    finally:
        conn.close()

    decrement_active_calls(trade["seller_pubkey"], trade["capability_hash"])
    resp = json.dumps({"output": output_data, "latency_us": latency_us, "status": "executed"}).encode()
    return pack_message(MSG_EXECUTE_RESPONSE, resp)


def handle_settle(payload: bytes) -> bytes:
    caller_pubkey, body_bytes = _tcp_authenticate(payload)
    if not caller_pubkey:
        return pack_error(0x02, b"invalid credentials")
    body = json.loads(body_bytes)

    trade_id = body["trade_id"]
    conn = get_connection()
    try:
        trade = conn.execute(
            "SELECT id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, latency_us, status FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        if trade is None:
            return pack_error(0x04, b"trade not found")
        if trade["buyer_pubkey"] != caller_pubkey:
            return pack_error(0x05, b"not the buyer")
        if trade["status"] != "executed":
            return pack_error(0x06, b"trade not in executed status")

        seller = conn.execute(
            "SELECT agent_pubkey, capability_hash, latency_bound_us, cu_staked FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
            (trade["seller_pubkey"], trade["capability_hash"]),
        ).fetchone()

        passed, reason = verify_trade(
            dict(trade), dict(seller) if seller else {"latency_bound_us": 0, "cu_staked": 0.0}, "output_present"
        )

        if passed:
            seller_receives, fee_cu = settle_trade(conn, dict(trade))
            check_sla_decoherence(conn, trade["seller_pubkey"], trade["capability_hash"])
            maybe_set_sla(conn, trade["seller_pubkey"], trade["capability_hash"])
            conn.commit()
            resp = json.dumps({"status": "completed", "seller_receives": seller_receives, "fee_cu": fee_cu}).encode()
        else:
            slash_bond(conn, dict(trade), dict(seller) if seller else {"cu_staked": 0.0}, reason)
            conn.commit()
            resp = json.dumps({"status": "violated", "reason": reason}).encode()
    finally:
        conn.close()
    return pack_message(MSG_EXECUTE_RESPONSE, resp)


def handle_query_events(payload: bytes) -> bytes:
    caller_pubkey, body_bytes = _tcp_authenticate(payload)
    if not caller_pubkey:
        return pack_error(0x02, b"invalid credentials")
    body = json.loads(body_bytes)
    conn = get_connection()
    try:
        row = conn.execute("SELECT pubkey FROM agents WHERE pubkey = ?", (body["agent_id"],)).fetchone()
        if row is None:
            return pack_error(0x07, b"agent not found")
        events = query_events(conn, body["agent_id"], event_type=body.get("event_type"), limit=body.get("limit", 100))
    finally:
        conn.close()
    resp = json.dumps({"agent_id": body["agent_id"], "events": events}).encode()
    return pack_message(MSG_EVENTS_RESPONSE, resp)


# ── V2 authenticated handlers ────────────────────────

def handle_register_agent_v2(payload: bytes) -> bytes:
    """Register an agent by Ed25519 public key. No auth block — pubkey IS the identity."""
    pubkey_hex = unpack_register_agent_v2(payload)
    now_ns = time.time_ns()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, NULL, 0.0, ?)",
            (pubkey_hex, now_ns),
        )
        record_event(conn, "agent_registered", json.dumps({"agent": pubkey_hex, "v2": True}))
        conn.commit()
    finally:
        conn.close()
    resp = json.dumps({"status": "registered", "pubkey": pubkey_hex}).encode()
    return pack_message(MSG_REGISTER_AGENT_V2, resp)


def _verify_v2(payload: bytes):
    """Unpack and verify a v2 auth block. Returns (pubkey_hex, inner) or raises."""
    try:
        pubkey_hex, sig_hex, ts_ns, inner = unpack_v2_auth(payload)
    except ValueError as exc:
        return None, None, pack_error(0x01, str(exc).encode()[:128])

    valid, reason = verify_request(sig_hex, inner, pubkey_hex, ts_ns)
    if not valid:
        msg = (reason if isinstance(reason, bytes) else reason.encode())[:128]
        return None, None, pack_error(0x02, msg)

    conn = get_connection()
    try:
        row = conn.execute("SELECT pubkey FROM agents WHERE pubkey = ?", (pubkey_hex,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None, None, pack_error(0x08, b"agent not registered")

    return pubkey_hex, inner, None


def handle_match_v2(payload: bytes) -> bytes:
    pubkey_hex, inner, err = _verify_v2(payload)
    if err is not None:
        return err

    cap_hash_bytes, max_price_cu = unpack_match_request_v2_payload(inner)
    cap_hash_hex = cap_hash_bytes.hex()
    price_limit = max_price_cu if max_price_cu > 0 else None

    seller = match_request(cap_hash_hex, price_limit, None)
    if seller is None:
        return pack_match_response(b'\x00' * 16, b'\x00' * 32, 0, 0)

    conn = get_connection()
    try:
        buyer_row = conn.execute("SELECT cu_balance FROM agents WHERE pubkey = ?", (pubkey_hex,)).fetchone()
        if buyer_row["cu_balance"] < seller["price_cu"]:
            return pack_match_response(b'\x00' * 16, b'\x00' * 32, 0, 2)

        trade_id = str(uuid.uuid4())
        trade_id_bytes = uuid.UUID(trade_id).bytes
        now_ns = time.time_ns()
        conn.execute("UPDATE agents SET cu_balance = cu_balance - ? WHERE pubkey = ?", (seller["price_cu"], pubkey_hex))
        conn.execute(
            "INSERT INTO trades (id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, start_ns, status) VALUES (?, ?, ?, ?, ?, ?, 'matched')",
            (trade_id, pubkey_hex, seller["agent_pubkey"], cap_hash_hex, seller["price_cu"], now_ns),
        )
        conn.execute(
            "INSERT INTO escrow (trade_id, buyer_pubkey, seller_pubkey, cu_amount, status) VALUES (?, ?, ?, ?, 'held')",
            (trade_id, pubkey_hex, seller["agent_pubkey"], seller["price_cu"]),
        )
        conn.execute(
            "UPDATE sellers SET active_calls = active_calls + 1 WHERE agent_pubkey = ? AND capability_hash = ?",
            (seller["agent_pubkey"], cap_hash_hex),
        )
        record_event(conn, "match_made", json.dumps({
            "trade_id": trade_id, "buyer": pubkey_hex, "seller": seller["agent_pubkey"],
            "capability_hash": cap_hash_hex, "price_cu": seller["price_cu"],
        }))
        conn.commit()
    finally:
        conn.close()

    increment_active_calls(seller["agent_pubkey"], cap_hash_hex)
    try:
        seller_bytes = bytes.fromhex(seller["agent_pubkey"])
    except ValueError:
        seller_bytes = seller["agent_pubkey"].encode().ljust(32, b'\x00')[:32]
    return pack_match_response(trade_id_bytes, seller_bytes, int(seller["price_cu"]), 1)


def handle_execute_v2(payload: bytes) -> bytes:
    pubkey_hex, inner, err = _verify_v2(payload)
    if err is not None:
        return err

    trade_id_bytes, input_data = unpack_execute_v2_payload(inner)
    trade_id = str(uuid.UUID(bytes=trade_id_bytes[:16]))
    input_str = input_data.decode('utf-8', errors='replace')

    conn = get_connection()
    try:
        trade = conn.execute(
            "SELECT buyer_pubkey, seller_pubkey, capability_hash, price_cu, status FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        if trade is None:
            return pack_error(0x04, b"trade not found")
        if trade["buyer_pubkey"] != pubkey_hex:
            return pack_error(0x05, b"not the buyer")
        if trade["status"] != "matched":
            return pack_error(0x06, b"trade not in matched status")

        start_ns = time.time_ns()
        output_data = f"executed:{input_str}".encode()
        end_ns = time.time_ns()
        latency_us = (end_ns - start_ns) // 1000

        conn.execute(
            "UPDATE trades SET start_ns = ?, end_ns = ?, latency_us = ?, status = 'executed' WHERE id = ?",
            (start_ns, end_ns, latency_us, trade_id),
        )
        conn.execute(
            "UPDATE sellers SET active_calls = MAX(0, active_calls - 1) WHERE agent_pubkey = ? AND capability_hash = ?",
            (trade["seller_pubkey"], trade["capability_hash"]),
        )
        record_event(conn, "trade_executed", json.dumps({
            "trade_id": trade_id, "buyer": pubkey_hex,
            "seller": trade["seller_pubkey"], "latency_us": latency_us,
        }))
        conn.commit()
    finally:
        conn.close()

    decrement_active_calls(trade["seller_pubkey"], trade["capability_hash"])
    return pack_execute_response(trade_id_bytes[:16], latency_us, 1, output_data)


# Message type → handler dispatch
MSG_SETTLE = 0x0A  # virtual type for settle over TCP

HANDLERS = {
    MSG_REGISTER_AGENT: handle_register_agent,
    MSG_REGISTER_SCHEMA: handle_register_schema,
    MSG_REGISTER_SELLER: handle_register_seller,
    MSG_MATCH_REQUEST: handle_match,
    MSG_EXECUTE: handle_execute,
    MSG_QUERY_EVENTS: handle_query_events,
    MSG_REGISTER_AGENT_V2: handle_register_agent_v2,
    MSG_MATCH_REQUEST_V2:  handle_match_v2,
    MSG_EXECUTE_V2:        handle_execute_v2,
}


async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    log("tcp_connect", addr=str(addr))
    try:
        while True:
            header = await reader.readexactly(HEADER_SIZE)
            msg_type, payload_len = unpack_header(header)
            payload = await reader.readexactly(payload_len)

            handler = HANDLERS.get(msg_type)
            if handler:
                response = handler(payload)
            else:
                response = pack_error(0x01, b"unknown message type")

            writer.write(response)
            await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    finally:
        log("tcp_disconnect", addr=str(addr))
        writer.close()
        await writer.wait_closed()


async def start_tcp_server(host="0.0.0.0", port=9000):
    init_db()
    server = await asyncio.start_server(handle_client, host, port)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(start_tcp_server())
