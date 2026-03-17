import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from wire import (
    pack_message, unpack_header, HEADER_SIZE,
    MSG_REGISTER_AGENT, MSG_MATCH_REQUEST, MSG_ERROR,
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
    import random
    types = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0xFF]
    for t in types:
        payload = bytes(random.getrandbits(8) for _ in range(32))
        msg = pack_message(t, payload)
        rt_type, rt_len = unpack_header(msg)
        assert rt_type == t
        assert rt_len == 32
        assert msg[HEADER_SIZE:HEADER_SIZE + rt_len] == payload
