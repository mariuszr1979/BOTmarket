# test_identity.py — Ed25519 identity system tests (Step 0)
import time
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from identity import generate_keypair, canonical_bytes, sign, verify, sign_request, verify_request


class TestKeypairGeneration:
    def test_keypair_lengths(self):
        priv, pub = generate_keypair()
        assert len(priv) == 64, "private key must be 64 hex chars (32 bytes)"
        assert len(pub) == 64, "public key must be 64 hex chars (32 bytes)"

    def test_keypair_valid_hex(self):
        priv, pub = generate_keypair()
        bytes.fromhex(priv)
        bytes.fromhex(pub)

    def test_keypair_unique(self):
        _, pub1 = generate_keypair()
        _, pub2 = generate_keypair()
        assert pub1 != pub2, "two keypairs must not produce same pubkey"

    def test_private_key_is_32_bytes(self):
        priv, _ = generate_keypair()
        assert len(bytes.fromhex(priv)) == 32

    def test_public_key_is_32_bytes(self):
        _, pub = generate_keypair()
        assert len(bytes.fromhex(pub)) == 32


class TestCanonicalBytes:
    def test_dict_sorted_keys(self):
        a = canonical_bytes({"z": 1, "a": 2})
        b = canonical_bytes({"a": 2, "z": 1})
        assert a == b, "different key ordering must produce same bytes"

    def test_dict_compact_separators(self):
        result = canonical_bytes({"key": "value"})
        assert result == b'{"key":"value"}'

    def test_string_passthrough(self):
        assert canonical_bytes("hello") == b"hello"

    def test_bytes_passthrough(self):
        assert canonical_bytes(b"raw") == b"raw"

    def test_nested_dict(self):
        a = canonical_bytes({"outer": {"z": 1, "a": 2}})
        b = canonical_bytes({"outer": {"a": 2, "z": 1}})
        assert a == b

    def test_deterministic_across_calls(self):
        body = {"capability_hash": "abc123", "price_cu": 10.0}
        assert canonical_bytes(body) == canonical_bytes(body)


class TestSignVerify:
    def test_sign_verify_roundtrip(self):
        priv, pub = generate_keypair()
        msg = b"test message"
        sig = sign(msg, priv)
        assert verify(sig, msg, pub) is True

    def test_signature_is_64_bytes(self):
        priv, _ = generate_keypair()
        sig = sign(b"msg", priv)
        assert len(sig) == 128, "signature must be 128 hex chars (64 bytes)"

    def test_invalid_signature_rejected(self):
        priv, pub = generate_keypair()
        sig = sign(b"original", priv)
        assert verify(sig, b"tampered", pub) is False

    def test_wrong_key_rejected(self):
        priv1, _ = generate_keypair()
        _, pub2 = generate_keypair()
        sig = sign(b"msg", priv1)
        assert verify(sig, b"msg", pub2) is False

    def test_corrupted_signature_rejected(self):
        priv, pub = generate_keypair()
        sig = sign(b"msg", priv)
        corrupted = "00" * 64  # all zeros
        assert verify(corrupted, b"msg", pub) is False

    def test_empty_message(self):
        priv, pub = generate_keypair()
        sig = sign(b"", priv)
        assert verify(sig, b"", pub) is True

    def test_large_message(self):
        priv, pub = generate_keypair()
        msg = b"x" * 100_000
        sig = sign(msg, priv)
        assert verify(sig, msg, pub) is True


class TestRequestSigning:
    def test_sign_verify_request_roundtrip(self):
        priv, pub = generate_keypair()
        body = {"capability_hash": "abc", "max_price_cu": 10.0}
        sig, ts = sign_request(body, priv)
        valid, reason = verify_request(sig, body, pub, ts)
        assert valid is True
        assert reason == "ok"

    def test_tampered_body_rejected(self):
        priv, pub = generate_keypair()
        body = {"key": "original"}
        sig, ts = sign_request(body, priv)
        valid, reason = verify_request(sig, {"key": "tampered"}, pub, ts)
        assert valid is False
        assert reason == "invalid_signature"

    def test_expired_timestamp_rejected(self):
        priv, pub = generate_keypair()
        body = {"key": "value"}
        old_ts = time.time_ns() - 60_000_000_000  # 60 seconds ago
        sig, ts = sign_request(body, priv, timestamp_ns=old_ts)
        valid, reason = verify_request(sig, body, pub, ts, max_age_sec=30)
        assert valid is False
        assert reason == "timestamp_expired"

    def test_fresh_timestamp_accepted(self):
        priv, pub = generate_keypair()
        body = {"key": "value"}
        sig, ts = sign_request(body, priv)
        valid, reason = verify_request(sig, body, pub, ts, max_age_sec=30)
        assert valid is True

    def test_wrong_key_rejected(self):
        priv1, _ = generate_keypair()
        _, pub2 = generate_keypair()
        body = {"key": "value"}
        sig, ts = sign_request(body, priv1)
        valid, reason = verify_request(sig, body, pub2, ts)
        assert valid is False
        assert reason == "invalid_signature"

    def test_string_body(self):
        priv, pub = generate_keypair()
        sig, ts = sign_request("plain string body", priv)
        valid, reason = verify_request(sig, "plain string body", pub, ts)
        assert valid is True

    def test_custom_timestamp(self):
        priv, pub = generate_keypair()
        body = {"data": 42}
        now = time.time_ns()
        sig, ts = sign_request(body, priv, timestamp_ns=now)
        assert ts == now
        valid, _ = verify_request(sig, body, pub, ts)
        assert valid is True


class TestEdgeCases:
    def test_no_private_key_leakage(self):
        """Exchange never sees private key — only pubkey and signatures."""
        priv, pub = generate_keypair()
        sig = sign(b"msg", priv)
        # Only pub and sig are needed for verification
        assert verify(sig, b"msg", pub) is True
        # priv is never passed to verify()

    def test_invalid_hex_in_verify(self):
        """Bad hex input should return False, not crash."""
        assert verify("not_hex", b"msg", "0" * 64) is False

    def test_short_key_in_verify(self):
        """Short key should return False, not crash."""
        priv, _ = generate_keypair()
        sig = sign(b"msg", priv)
        assert verify(sig, b"msg", "abcd") is False
