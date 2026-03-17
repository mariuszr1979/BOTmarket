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


def pack_message(msg_type: int, payload: bytes) -> bytes:
    header = struct.pack(HEADER_FORMAT, msg_type, len(payload))
    return header + payload


def unpack_header(data: bytes):
    if len(data) < HEADER_SIZE:
        return None, None
    msg_type, length = struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])
    return msg_type, length
