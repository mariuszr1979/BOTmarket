import struct

# Wire format v1: [msg_type: u8][payload_length: u32][payload: bytes]
# Wire format v2: [msg_type: u8][payload_length: u32][pubkey: 32B][signature: 64B][timestamp: 8B][payload: bytes]
# Header = 5 bytes, always. Big-endian (network order).

HEADER_FORMAT = '!BL'  # u8 msg_type + u32 payload_length
HEADER_SIZE   = 5      # 1 + 4 bytes

# Auth header appended after wire header in v2 authenticated packets
AUTH_SIZE = 104  # 32 (pubkey) + 64 (signature) + 8 (timestamp_ns)

# Message type constants — v1 (unchanged)
MSG_REGISTER_AGENT   = 0x01
MSG_REGISTER_SCHEMA  = 0x02
MSG_REGISTER_SELLER  = 0x03
MSG_MATCH_REQUEST    = 0x04
MSG_MATCH_RESPONSE   = 0x05
MSG_EXECUTE          = 0x06
MSG_EXECUTE_RESPONSE = 0x07
MSG_QUERY_EVENTS     = 0x08
MSG_EVENTS_RESPONSE  = 0x09
MSG_ERROR            = 0xFF

# Message type constants — v2 (Ed25519 authenticated)
MSG_REGISTER_AGENT_V2 = 0x11   # payload: pubkey(32B) — registers by Ed25519 pubkey
MSG_MATCH_REQUEST_V2  = 0x14   # auth header + payload: cap_hash(32) + max_price_cu(8)
MSG_EXECUTE_V2        = 0x16   # auth header + payload: trade_id(32) + input_data(N)

# Payload formats (big-endian)
# agent_id and capability_hash are 32-byte blobs (SHA-256 or UUID padded)
MATCH_REQ_FORMAT   = '!32s32sQ'    # agent_id(32) + cap_hash(32) + max_price_cu(8) = 72
MATCH_RESP_FORMAT  = '!32s32sQB'   # trade_id(32) + seller(32) + price_cu(8) + status(1) = 73
REGISTER_SELLER_FORMAT = '!32s32sQI'  # agent_id(32) + cap_hash(32) + price_cu(8) + capacity(4) = 76
EXECUTE_FORMAT     = '!32s'        # trade_id(32) + variable input follows
EXECUTE_RESP_FORMAT = '!32sQB'     # trade_id(32) + latency_us(8) + status(1) = 41, + variable output
ERROR_FORMAT       = '!BH'         # error_code(1) + msg_length(2) = 3, + variable message


def pack_message(msg_type: int, payload: bytes) -> bytes:
    header = struct.pack(HEADER_FORMAT, msg_type, len(payload))
    return header + payload


def unpack_header(data: bytes):
    if len(data) < HEADER_SIZE:
        return None, None
    msg_type, length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    return msg_type, length


# ── Typed pack/unpack ────────────────────────────────

def _pad32(s: bytes) -> bytes:
    """Pad or truncate to exactly 32 bytes."""
    return s[:32].ljust(32, b'\x00')


def pack_register_agent(agent_id: bytes) -> bytes:
    return pack_message(MSG_REGISTER_AGENT, _pad32(agent_id))


def unpack_register_agent(payload: bytes) -> bytes:
    return payload[:32]


def pack_register_schema(input_schema: bytes, output_schema: bytes) -> bytes:
    payload = struct.pack('!H', len(input_schema)) + input_schema + struct.pack('!H', len(output_schema)) + output_schema
    return pack_message(MSG_REGISTER_SCHEMA, payload)


def unpack_register_schema(payload: bytes) -> tuple[bytes, bytes]:
    in_len = struct.unpack('!H', payload[:2])[0]
    input_schema = payload[2:2 + in_len]
    offset = 2 + in_len
    out_len = struct.unpack('!H', payload[offset:offset + 2])[0]
    output_schema = payload[offset + 2:offset + 2 + out_len]
    return input_schema, output_schema


def pack_register_seller(agent_id: bytes, cap_hash: bytes, price_cu: int, capacity: int) -> bytes:
    payload = struct.pack(REGISTER_SELLER_FORMAT, _pad32(agent_id), _pad32(cap_hash), price_cu, capacity)
    return pack_message(MSG_REGISTER_SELLER, payload)


def unpack_register_seller(payload: bytes) -> tuple[bytes, bytes, int, int]:
    return struct.unpack(REGISTER_SELLER_FORMAT, payload[:76])


def pack_match_request(agent_id: bytes, cap_hash: bytes, max_price_cu: int) -> bytes:
    payload = struct.pack(MATCH_REQ_FORMAT, _pad32(agent_id), _pad32(cap_hash), max_price_cu)
    return pack_message(MSG_MATCH_REQUEST, payload)


def unpack_match_request(payload: bytes) -> tuple[bytes, bytes, int]:
    return struct.unpack(MATCH_REQ_FORMAT, payload[:72])


def pack_match_response(trade_id: bytes, seller: bytes, price_cu: int, status: int) -> bytes:
    payload = struct.pack(MATCH_RESP_FORMAT, _pad32(trade_id), _pad32(seller), price_cu, status)
    return pack_message(MSG_MATCH_RESPONSE, payload)


def unpack_match_response(payload: bytes) -> tuple[bytes, bytes, int, int]:
    return struct.unpack(MATCH_RESP_FORMAT, payload[:73])


def pack_execute(trade_id: bytes, input_data: bytes) -> bytes:
    payload = _pad32(trade_id) + input_data
    return pack_message(MSG_EXECUTE, payload)


def unpack_execute(payload: bytes) -> tuple[bytes, bytes]:
    return payload[:32], payload[32:]


def pack_execute_response(trade_id: bytes, latency_us: int, status: int, output: bytes) -> bytes:
    payload = struct.pack(EXECUTE_RESP_FORMAT, _pad32(trade_id), latency_us, status) + output
    return pack_message(MSG_EXECUTE_RESPONSE, payload)


def unpack_execute_response(payload: bytes) -> tuple[bytes, int, int, bytes]:
    trade_id, latency_us, status = struct.unpack(EXECUTE_RESP_FORMAT, payload[:41])
    return trade_id, latency_us, status, payload[41:]


def pack_query_events(agent_id: bytes, event_type: bytes = b'') -> bytes:
    payload = _pad32(agent_id) + struct.pack('!H', len(event_type)) + event_type
    return pack_message(MSG_QUERY_EVENTS, payload)


def unpack_query_events(payload: bytes) -> tuple[bytes, bytes]:
    agent_id = payload[:32]
    et_len = struct.unpack('!H', payload[32:34])[0]
    event_type = payload[34:34 + et_len]
    return agent_id, event_type


def pack_events_response(events_data: bytes) -> bytes:
    return pack_message(MSG_EVENTS_RESPONSE, events_data)


def unpack_events_response(payload: bytes) -> bytes:
    return payload


def pack_error(error_code: int, message: bytes) -> bytes:
    payload = struct.pack('!B', error_code) + message
    return pack_message(MSG_ERROR, payload)


def unpack_error(payload: bytes) -> tuple[int, bytes]:
    return payload[0], payload[1:]


# ── V2 authenticated pack/unpack ─────────────────────

# V2 packet layout (after the 5-byte wire header):
#   [pubkey: 32B][signature: 64B][timestamp_ns: 8B][payload: NB]
# The payload_length in the wire header covers the auth block + payload.

_AUTH_FORMAT = '!32s64sQ'  # pubkey(32) + sig(64) + timestamp_ns(8)


def pack_v2_message(msg_type: int, pubkey_hex: str, sig_hex: str,
                    timestamp_ns: int, payload: bytes) -> bytes:
    """Pack an authenticated v2 message."""
    pubkey_bytes = bytes.fromhex(pubkey_hex)
    sig_bytes    = bytes.fromhex(sig_hex)
    auth_block   = struct.pack(_AUTH_FORMAT, pubkey_bytes, sig_bytes, timestamp_ns)
    full_payload = auth_block + payload
    return pack_message(msg_type, full_payload)


def unpack_v2_auth(data: bytes) -> tuple[str, str, int, bytes]:
    """Split v2 payload into (pubkey_hex, sig_hex, timestamp_ns, inner_payload).
    data is the raw payload after the 5-byte wire header."""
    if len(data) < AUTH_SIZE:
        raise ValueError(f"v2 payload too short: {len(data)} < {AUTH_SIZE}")
    pubkey_bytes, sig_bytes, timestamp_ns = struct.unpack(_AUTH_FORMAT, data[:AUTH_SIZE])
    return pubkey_bytes.hex(), sig_bytes.hex(), timestamp_ns, data[AUTH_SIZE:]


def pack_register_agent_v2(pubkey_hex: str) -> bytes:
    """V2 agent registration: payload is just the 32-byte pubkey (no auth block)."""
    return pack_message(MSG_REGISTER_AGENT_V2, bytes.fromhex(pubkey_hex))


def unpack_register_agent_v2(payload: bytes) -> str:
    """Returns pubkey_hex."""
    return payload[:32].hex()


# V2 match request inner payload: cap_hash(32) + max_price_cu(8)
_MATCH_V2_FORMAT = '!32sQ'
_MATCH_V2_SIZE   = 40


def pack_match_request_v2(pubkey_hex: str, sig_hex: str, timestamp_ns: int,
                           cap_hash: bytes, max_price_cu: int) -> bytes:
    payload = struct.pack(_MATCH_V2_FORMAT, _pad32(cap_hash), max_price_cu)
    return pack_v2_message(MSG_MATCH_REQUEST_V2, pubkey_hex, sig_hex, timestamp_ns, payload)


def unpack_match_request_v2_payload(inner: bytes) -> tuple[bytes, int]:
    """inner is the payload after the auth block."""
    cap_hash, max_price_cu = struct.unpack(_MATCH_V2_FORMAT, inner[:_MATCH_V2_SIZE])
    return cap_hash, max_price_cu


# V2 execute inner payload: trade_id(32) + input_data(N)
def pack_execute_v2(pubkey_hex: str, sig_hex: str, timestamp_ns: int,
                    trade_id: bytes, input_data: bytes) -> bytes:
    payload = _pad32(trade_id) + input_data
    return pack_v2_message(MSG_EXECUTE_V2, pubkey_hex, sig_hex, timestamp_ns, payload)


def unpack_execute_v2_payload(inner: bytes) -> tuple[bytes, bytes]:
    """inner is the payload after the auth block."""
    return inner[:32], inner[32:]
