# identity.py — Ed25519 cryptographic identity (keygen, sign, verify, canonical)
# One module, one concern. Pure functions. No state. No database.
import json
import time

from nacl.signing import SigningKey, VerifyKey
from nacl.exceptions import BadSignatureError


def generate_keypair():
    """Generate Ed25519 keypair. Returns (private_key_hex, public_key_hex)."""
    signing_key = SigningKey.generate()
    private_hex = signing_key.encode().hex()  # 32 bytes → 64 hex chars
    public_hex = signing_key.verify_key.encode().hex()  # 32 bytes → 64 hex chars
    return private_hex, public_hex


def canonical_bytes(body):
    """Deterministic serialization: sorted keys, compact separators, UTF-8 bytes.
    Same approach as schema hashing — canonical, reproducible."""
    if isinstance(body, str):
        return body.encode("utf-8")
    if isinstance(body, bytes):
        return body
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(message_bytes, private_key_hex):
    """Sign bytes with Ed25519 private key. Returns signature hex (128 chars = 64 bytes)."""
    signing_key = SigningKey(bytes.fromhex(private_key_hex))
    signed = signing_key.sign(message_bytes)
    return signed.signature.hex()


def verify(signature_hex, message_bytes, public_key_hex):
    """Verify Ed25519 signature. Returns True if valid, False otherwise."""
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(message_bytes, bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError):
        return False


def sign_request(body, private_key_hex, timestamp_ns=None):
    """Sign a request body with timestamp for replay protection.
    Returns (signature_hex, timestamp_ns)."""
    if timestamp_ns is None:
        timestamp_ns = time.time_ns()
    canonical = canonical_bytes(body)
    message = str(timestamp_ns).encode("utf-8") + b":" + canonical
    sig = sign(message, private_key_hex)
    return sig, timestamp_ns


def verify_request(signature_hex, body, public_key_hex, timestamp_ns, max_age_sec=30):
    """Verify a signed request with replay protection.
    Returns (valid: bool, reason: str)."""
    # Replay check
    now_ns = time.time_ns()
    age_sec = abs(now_ns - timestamp_ns) / 1_000_000_000
    if age_sec > max_age_sec:
        return False, "timestamp_expired"

    canonical = canonical_bytes(body)
    message = str(timestamp_ns).encode("utf-8") + b":" + canonical
    if verify(signature_hex, message, public_key_hex):
        return True, "ok"
    return False, "invalid_signature"
