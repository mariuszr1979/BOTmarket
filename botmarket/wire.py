import struct

# Wire format: [msg_type: u8][payload_length: u32][payload: bytes]
# Header = 5 bytes, always. Big-endian (network order).

HEADER_FORMAT = '!BL'  # u8 msg_type + u32 payload_length
HEADER_SIZE   = 5      # 1 + 4 bytes

# Message type constants
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
