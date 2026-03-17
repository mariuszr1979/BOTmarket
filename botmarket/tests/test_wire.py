import sys
import os
import random
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wire import (
    pack_message, unpack_header, HEADER_SIZE, HEADER_FORMAT,
    MSG_REGISTER_AGENT, MSG_REGISTER_SCHEMA, MSG_REGISTER_SELLER,
    MSG_MATCH_REQUEST, MSG_MATCH_RESPONSE, MSG_EXECUTE, MSG_EXECUTE_RESPONSE,
    MSG_QUERY_EVENTS, MSG_EVENTS_RESPONSE, MSG_ERROR,
    pack_register_agent, unpack_register_agent,
    pack_register_schema, unpack_register_schema,
    pack_register_seller, unpack_register_seller,
    pack_match_request, unpack_match_request,
    pack_match_response, unpack_match_response,
    pack_execute, unpack_execute,
    pack_execute_response, unpack_execute_response,
    pack_query_events, unpack_query_events,
    pack_events_response, unpack_events_response,
    pack_error, unpack_error,
)


def test_pack_unpack_roundtrip():
    payload = b"hello"
    msg = pack_message(MSG_REGISTER_AGENT, payload)
    msg_type, length = unpack_header(msg)
    assert msg_type == MSG_REGISTER_AGENT
    assert length == len(payload)
    assert msg[HEADER_SIZE:HEADER_SIZE + length] == payload


def test_header_size_is_five():
    assert HEADER_SIZE == 5


def test_empty_payload():
    msg = pack_message(MSG_REGISTER_AGENT, b"")
    msg_type, length = unpack_header(msg)
    assert msg_type == MSG_REGISTER_AGENT
    assert length == 0


def test_truncated_header_returns_none():
    msg_type, length = unpack_header(b"\x01\x00")
    assert msg_type is None
    assert length is None


def test_all_message_types_survive_roundtrip():
    types = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0xFF]
    for t in types:
        payload = bytes(random.getrandbits(8) for _ in range(32))
        msg = pack_message(t, payload)
        rt_type, rt_len = unpack_header(msg)
        assert rt_type == t
        assert rt_len == 32
        assert msg[HEADER_SIZE:HEADER_SIZE + rt_len] == payload


# ── Step 9: Typed pack/unpack tests ──────────────────


def test_match_request_exact_size():
    """Match request packs to exactly 77 bytes (5 header + 72 payload)."""
    msg = pack_match_request(b"A" * 32, b"B" * 32, 25)
    assert len(msg) == 77


def test_match_response_exact_size():
    """Match response packs to exactly 78 bytes (5 header + 73 payload)."""
    msg = pack_match_response(b"T" * 32, b"S" * 32, 100, 1)
    assert len(msg) == 78


def test_match_request_roundtrip():
    agent_id = b"agent123" + b"\x00" * 24
    cap_hash = b"hash456" + b"\x00" * 25
    max_price = 25000
    msg = pack_match_request(agent_id, cap_hash, max_price)
    mt, length = unpack_header(msg)
    assert mt == MSG_MATCH_REQUEST
    aid, ch, mp = unpack_match_request(msg[HEADER_SIZE:])
    assert aid == agent_id
    assert ch == cap_hash
    assert mp == max_price


def test_match_response_roundtrip():
    trade_id = b"T" * 32
    seller = b"S" * 32
    price = 500
    status = 1
    msg = pack_match_response(trade_id, seller, price, status)
    mt, length = unpack_header(msg)
    assert mt == MSG_MATCH_RESPONSE
    tid, sel, pr, st = unpack_match_response(msg[HEADER_SIZE:])
    assert tid == trade_id
    assert sel == seller
    assert pr == price
    assert st == status


def test_register_agent_roundtrip():
    agent_id = b"myagent" + b"\x00" * 25
    msg = pack_register_agent(agent_id)
    mt, length = unpack_header(msg)
    assert mt == MSG_REGISTER_AGENT
    assert length == 32
    result = unpack_register_agent(msg[HEADER_SIZE:])
    assert result == agent_id


def test_register_schema_roundtrip():
    inp = b'{"type":"object"}'
    out = b'{"type":"string"}'
    msg = pack_register_schema(inp, out)
    mt, _ = unpack_header(msg)
    assert mt == MSG_REGISTER_SCHEMA
    r_inp, r_out = unpack_register_schema(msg[HEADER_SIZE:])
    assert r_inp == inp
    assert r_out == out


def test_register_seller_roundtrip():
    aid = b"A" * 32
    ch = b"C" * 32
    price = 42000
    cap = 10
    msg = pack_register_seller(aid, ch, price, cap)
    mt, length = unpack_header(msg)
    assert mt == MSG_REGISTER_SELLER
    assert length == 76
    r_aid, r_ch, r_price, r_cap = unpack_register_seller(msg[HEADER_SIZE:])
    assert r_aid == aid
    assert r_ch == ch
    assert r_price == price
    assert r_cap == cap


def test_execute_roundtrip():
    trade_id = b"X" * 32
    input_data = b"compute this please"
    msg = pack_execute(trade_id, input_data)
    mt, _ = unpack_header(msg)
    assert mt == MSG_EXECUTE
    r_tid, r_inp = unpack_execute(msg[HEADER_SIZE:])
    assert r_tid == trade_id
    assert r_inp == input_data


def test_execute_response_roundtrip():
    trade_id = b"Y" * 32
    latency = 1500
    status = 1
    output = b"result data here"
    msg = pack_execute_response(trade_id, latency, status, output)
    mt, _ = unpack_header(msg)
    assert mt == MSG_EXECUTE_RESPONSE
    r_tid, r_lat, r_st, r_out = unpack_execute_response(msg[HEADER_SIZE:])
    assert r_tid == trade_id
    assert r_lat == latency
    assert r_st == status
    assert r_out == output


def test_query_events_roundtrip():
    agent_id = b"Q" * 32
    event_type = b"match_made"
    msg = pack_query_events(agent_id, event_type)
    mt, _ = unpack_header(msg)
    assert mt == MSG_QUERY_EVENTS
    r_aid, r_et = unpack_query_events(msg[HEADER_SIZE:])
    assert r_aid == agent_id
    assert r_et == event_type


def test_query_events_no_filter():
    agent_id = b"Q" * 32
    msg = pack_query_events(agent_id)
    r_aid, r_et = unpack_query_events(msg[HEADER_SIZE:])
    assert r_aid == agent_id
    assert r_et == b''


def test_events_response_roundtrip():
    data = b'[{"seq":1,"event_type":"match_made"}]'
    msg = pack_events_response(data)
    mt, _ = unpack_header(msg)
    assert mt == MSG_EVENTS_RESPONSE
    assert unpack_events_response(msg[HEADER_SIZE:]) == data


def test_error_roundtrip():
    code = 0x01
    message = b"unknown message type"
    msg = pack_error(code, message)
    mt, _ = unpack_header(msg)
    assert mt == MSG_ERROR
    r_code, r_msg = unpack_error(msg[HEADER_SIZE:])
    assert r_code == code
    assert r_msg == message


def test_big_endian_byte_order():
    """Verify big-endian (network order) encoding."""
    msg = pack_message(MSG_MATCH_REQUEST, b"\x00" * 72)
    # Header: msg_type=0x04, length=72 (0x00000048)
    assert msg[0] == 0x04
    assert msg[1:5] == b"\x00\x00\x00\x48"


def test_1000_random_messages_roundtrip():
    """Pack 1000 random messages → unpack all → 100% match."""
    types = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0xFF]
    for _ in range(1000):
        t = random.choice(types)
        size = random.randint(0, 256)
        payload = bytes(random.getrandbits(8) for _ in range(size))
        msg = pack_message(t, payload)
        rt_type, rt_len = unpack_header(msg)
        assert rt_type == t
        assert rt_len == size
        assert msg[HEADER_SIZE:HEADER_SIZE + rt_len] == payload


def test_no_external_dependencies():
    """wire.py uses only stdlib struct — verify by checking imports."""
    import wire
    source = open(wire.__file__).read()
    # Only stdlib struct should be imported
    assert "import struct" in source
    # No third-party imports
    for bad in ["import msgpack", "import protobuf", "import cbor", "import json"]:
        assert bad not in source


def test_pad32_truncates_long_input():
    """Inputs longer than 32 bytes get truncated."""
    long_id = b"A" * 64
    msg = pack_register_agent(long_id)
    result = unpack_register_agent(msg[HEADER_SIZE:])
    assert len(result) == 32
    assert result == b"A" * 32


def test_pad32_pads_short_input():
    """Inputs shorter than 32 bytes get zero-padded."""
    short_id = b"AB"
    msg = pack_register_agent(short_id)
    result = unpack_register_agent(msg[HEADER_SIZE:])
    assert len(result) == 32
    assert result == b"AB" + b"\x00" * 30
