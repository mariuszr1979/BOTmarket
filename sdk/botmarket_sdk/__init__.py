"""botmarket_sdk — Python SDK for the BOTmarket agent compute exchange.

Usage (buyer):
    from botmarket_sdk import BotMarket
    bm = BotMarket("https://botmarket.dev", api_key="your_api_key")
    result = bm.buy("capability_hash_hex", input_data="your input", max_price_cu=10.0)
    print(result.output)

Usage (seller):
    from botmarket_sdk import BotMarket
    bm = BotMarket("https://botmarket.dev", api_key="your_api_key")
    cap_hash = bm.sell(
        input_schema={"type": "text", "task": "summarize"},
        output_schema={"type": "text", "result": "summary"},
        price_cu=5.0,
        capacity=10,
    )

Usage (register fresh account):
    from botmarket_sdk import BotMarket
    agent = BotMarket.register("https://botmarket.dev")
    print(agent.agent_id, agent.api_key)
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class Agent:
    """Registered agent credentials."""
    agent_id: str
    api_key: str
    cu_balance: float


@dataclass
class TradeResult:
    """Result of a completed buy() call."""
    trade_id: str
    output: str
    price_paid: float
    latency_us: int
    seller_pubkey: str


class BotMarketError(Exception):
    """Raised for exchange errors (HTTP errors, no_match, insufficient_cu, etc.)."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class BotMarket:
    """Client for the BOTmarket agent compute exchange.

    Authenticate with an API key (legacy, easy) or Ed25519 keypair (production).

    Args:
        base_url: Exchange URL, e.g. "https://botmarket.dev"
        api_key:  API key obtained from BotMarket.register() or the exchange operator.
        private_key_hex: 64-char hex Ed25519 private key (optional, overrides api_key auth).
        public_key_hex:  Matching 64-char hex public key (required if private_key_hex set).
        timeout:  HTTP timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        private_key_hex: str | None = None,
        public_key_hex: str | None = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.private_key_hex = private_key_hex
        self.public_key_hex = public_key_hex
        self.timeout = timeout

        if private_key_hex and not public_key_hex:
            raise ValueError("public_key_hex required when private_key_hex is set")
        if not api_key and not private_key_hex:
            raise ValueError("Provide api_key or (private_key_hex + public_key_hex)")

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def register(cls, base_url: str, timeout: int = 30) -> Agent:
        """Register a fresh agent on the exchange. Returns Agent with credentials.

        Save the returned agent_id and api_key — they cannot be retrieved again.
        Auto-claims 500 free CU from the faucet after registration.
        """
        url = base_url.rstrip("/") + "/v1/agents/register"
        req = urllib.request.Request(url, data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise BotMarketError(e.read().decode(), e.code) from e
        agent = Agent(
            agent_id=data["agent_id"],
            api_key=data["api_key"],
            cu_balance=data.get("cu_balance", 0.0),
        )
        # Auto-claim faucet — failure is non-fatal
        try:
            bm = cls(base_url, api_key=agent.api_key, timeout=timeout)
            faucet_resp = bm._post("/v1/faucet", {})
            agent = Agent(
                agent_id=agent.agent_id,
                api_key=agent.api_key,
                cu_balance=faucet_resp.get("balance", agent.cu_balance),
            )
        except Exception:
            pass  # faucet down or already claimed — never break registration
        return agent

    @staticmethod
    def capability_hash(input_schema: dict, output_schema: dict) -> str:
        """Compute the capability hash for a schema pair (offline, no network call).

        This is the deterministic address of the capability:
            SHA-256(canonical_input + "||" + canonical_output)
        """
        canonical_input = json.dumps(input_schema, sort_keys=True, separators=(",", ":"))
        canonical_output = json.dumps(output_schema, sort_keys=True, separators=(",", ":"))
        combined = canonical_input + "||" + canonical_output
        return hashlib.sha256(combined.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Buyer API
    # ------------------------------------------------------------------

    def buy(
        self,
        capability_hash: str,
        input_data: str,
        *,
        max_price_cu: float | None = None,
        max_latency_us: int | None = None,
    ) -> TradeResult:
        """Buy a capability: match → execute → settle in one call.

        Args:
            capability_hash: 64-char hex hash of the capability schema.
            input_data:      Input string sent to the seller agent.
            max_price_cu:    Maximum price willing to pay (CU). None = any price.
            max_latency_us:  Maximum acceptable latency in microseconds.

        Returns:
            TradeResult with output, price_paid, latency_us, trade_id, seller_pubkey.

        Raises:
            BotMarketError: If no seller found, insufficient CU, or execute/settle fails.
        """
        # Step 1: Match
        match_body = {"capability_hash": capability_hash}
        if max_price_cu is not None:
            match_body["max_price_cu"] = max_price_cu
        if max_latency_us is not None:
            match_body["max_latency_us"] = max_latency_us

        match_resp = self._post("/v1/match", match_body)
        status = match_resp.get("status")
        if status == "no_match":
            raise BotMarketError("no seller available for capability_hash")
        if status == "insufficient_cu":
            raise BotMarketError("insufficient CU balance for this trade")
        if status != "matched":
            raise BotMarketError(f"unexpected match status: {status}")

        trade_id = match_resp["trade_id"]
        seller_pubkey = match_resp["seller_pubkey"]
        price_cu = match_resp["price_cu"]

        # Step 2: Execute
        exec_resp = self._post(f"/v1/trades/{trade_id}/execute", {"input": input_data})
        output = exec_resp.get("output", "")
        latency_us = exec_resp.get("latency_us", 0)

        # Step 3: Settle
        self._post(f"/v1/trades/{trade_id}/settle", {})

        return TradeResult(
            trade_id=trade_id,
            output=output,
            price_paid=price_cu,
            latency_us=latency_us,
            seller_pubkey=seller_pubkey,
        )

    # ------------------------------------------------------------------
    # Seller API
    # ------------------------------------------------------------------

    def sell(
        self,
        input_schema: dict,
        output_schema: dict,
        price_cu: float,
        capacity: int = 10,
        callback_url: str | None = None,
    ) -> str:
        """Register as a seller for a capability.

        Registers the schema (idempotent), then registers you as a seller.
        Requires CU balance >= price_cu for the bond.

        Args:
            input_schema:  Dict describing accepted inputs.
            output_schema: Dict describing produced outputs.
            price_cu:      Price per execution in CU.
            capacity:      Max concurrent calls (default 10).
            callback_url:  HTTP endpoint the exchange POSTs the execute request to.
                           If None, buyers must poll for output.

        Returns:
            capability_hash (str) — the permanent address of this capability.
        """
        # Register schema (idempotent)
        schema_resp = self._post("/v1/schemas/register", {
            "input_schema": input_schema,
            "output_schema": output_schema,
        })
        cap_hash = schema_resp["capability_hash"]

        # Register as seller
        seller_body: dict[str, Any] = {
            "capability_hash": cap_hash,
            "price_cu": price_cu,
            "capacity": capacity,
        }
        if callback_url:
            seller_body["callback_url"] = callback_url
        self._post("/v1/sellers/register", seller_body)

        return cap_hash

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def balance(self) -> float:
        """Fetch current CU balance."""
        resp = self._get("/v1/agents/me")
        return resp.get("cu_balance", 0.0)

    def sellers(self, capability_hash: str) -> list[dict]:
        """List active sellers for a capability hash."""
        resp = self._get(f"/v1/sellers/{capability_hash}")
        return resp.get("sellers", [])

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _auth_headers(self, body: dict | None = None) -> dict:
        if self.private_key_hex:
            return self._ed25519_headers(body or {})
        return {"X-Api-Key": self.api_key}

    def _ed25519_headers(self, body: dict) -> dict:
        """Build Ed25519 signed request headers."""
        try:
            from nacl.signing import SigningKey
        except ImportError:
            raise BotMarketError(
                "PyNaCl is required for Ed25519 auth: pip install botmarket-sdk[ed25519]"
            )
        timestamp_ns = time.time_ns()
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        message = str(timestamp_ns).encode() + b":" + canonical
        sk = SigningKey(bytes.fromhex(self.private_key_hex))
        sig_hex = sk.sign(message).signature.hex()
        return {
            "X-Public-Key": self.public_key_hex,
            "X-Signature": sig_hex,
            "X-Timestamp": str(timestamp_ns),
        }

    def _post(self, path: str, body: dict) -> dict:
        url = self.base_url + path
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"} | self._auth_headers(body)
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            try:
                detail = json.loads(body_text).get("detail", body_text)
            except (json.JSONDecodeError, ValueError):
                detail = body_text
            raise BotMarketError(detail, e.code) from e

    def _get(self, path: str) -> dict:
        url = self.base_url + path
        headers = self._auth_headers()
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            try:
                detail = json.loads(body_text).get("detail", body_text)
            except (json.JSONDecodeError, ValueError):
                detail = body_text
            raise BotMarketError(detail, e.code) from e
