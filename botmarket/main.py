from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import uuid
import time
import urllib.parse

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from db import init_db, get_connection
from log import log
from events import record_event, query_events
from constants import FAUCET_FIRST_CU, FAUCET_DRIP_CU, FAUCET_MAX_CU, FAUCET_WINDOW_NS
from matching import rebuild_seller_tables, add_seller, get_sellers, match_request, increment_active_calls, decrement_active_calls
from verification import verify_trade
from settlement import settle_trade, slash_bond, maybe_set_sla, check_sla_decoherence
from identity import verify_request, canonical_bytes


@asynccontextmanager
async def lifespan(app):
    conn = init_db()
    rebuild_seller_tables(conn)
    conn.close()
    yield


app = FastAPI(title="BOTmarket", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def authenticate(x_api_key=None, x_public_key=None, x_signature=None, x_timestamp=None, body=b""):
    """Dual-mode auth: Ed25519 signature (new) or API key (legacy).
    Ed25519 takes priority when both are present."""
    # Ed25519 path
    if x_public_key is not None and x_signature is not None and x_timestamp is not None:
        try:
            ts_ns = int(x_timestamp)
        except (ValueError, TypeError):
            raise HTTPException(status_code=401, detail="invalid timestamp")
        valid, reason = verify_request(x_signature, body, x_public_key, ts_ns)
        if not valid:
            raise HTTPException(status_code=401, detail=reason)
        conn = get_connection()
        try:
            row = conn.execute("SELECT pubkey FROM agents WHERE pubkey = ?", (x_public_key,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise HTTPException(status_code=401, detail="unknown public key")
        return x_public_key

    # Legacy API key path
    if x_api_key is not None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT pubkey FROM agents WHERE api_key = ?", (x_api_key,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise HTTPException(status_code=401, detail="invalid api key")
        return row["pubkey"]

    raise HTTPException(status_code=401, detail="missing authentication")


async def get_auth(request: Request,
                   x_api_key: str | None = Header(default=None),
                   x_public_key: str | None = Header(default=None),
                   x_signature: str | None = Header(default=None),
                   x_timestamp: str | None = Header(default=None)) -> str:
    """FastAPI dependency: extract auth headers + raw body, return authenticated pubkey."""
    body_bytes = await request.body()
    # Parse JSON for canonical signature verification (so any JSON formatting matches)
    if body_bytes:
        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            body = body_bytes
    else:
        body = b""
    return authenticate(x_api_key, x_public_key, x_signature, x_timestamp, body=body)


@app.get("/v1/health")
def health():
    db_status = "ok"
    try:
        conn = get_connection()
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
    except Exception:
        db_status = "error"
    return {"status": "ok" if db_status == "ok" else "degraded", "db": db_status}


_LIVE_HTML = Path(__file__).resolve().parent.parent / "slides" / "live.html"
_SKILL_MD  = Path(__file__).resolve().parent / "skill.md"


@app.get("/skill.md", response_class=PlainTextResponse)
def skill_md():
    """LLM-native onboarding: read this URL and follow instructions to join the exchange."""
    return _SKILL_MD.read_text()


@app.get("/live", response_class=HTMLResponse)
def live_dashboard():
    return _LIVE_HTML.read_text()


@app.post("/v1/agents/register", status_code=201)
def register_agent():
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

    log("agent_registered", agent_id=pubkey)
    return {"agent_id": pubkey, "api_key": api_key, "cu_balance": 0.0}


class RegisterAgentV2Request(BaseModel):
    public_key: str


@app.post("/v1/agents/register/v2", status_code=201)
def register_agent_v2(body: RegisterAgentV2Request):
    """Ed25519 agent registration. Public key IS the identity — no API key generated."""
    pk = body.public_key
    if len(pk) != 64:
        raise HTTPException(status_code=400, detail="public_key must be 64 hex chars (32 bytes)")
    try:
        bytes.fromhex(pk)
    except ValueError:
        raise HTTPException(status_code=400, detail="public_key must be valid hex")

    now_ns = time.time_ns()
    conn = get_connection()
    try:
        existing = conn.execute("SELECT pubkey FROM agents WHERE pubkey = ?", (pk,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="agent already registered")
        conn.execute(
            "INSERT INTO agents (pubkey, api_key, cu_balance, registered_at) VALUES (?, NULL, 0.0, ?)",
            (pk, now_ns),
        )
        record_event(conn, "agent_registered", json.dumps({"agent": pk, "auth": "ed25519"}))
        conn.commit()
    finally:
        conn.close()

    log("agent_registered_v2", agent_id=pk)
    return {"agent_id": pk, "cu_balance": 0.0}


class SchemaRegisterRequest(BaseModel):
    input_schema: dict
    output_schema: dict


@app.post("/v1/schemas/register", status_code=201)
async def register_schema(body: SchemaRegisterRequest, agent_pubkey: str = Depends(get_auth)):

    canonical_input = json.dumps(body.input_schema, sort_keys=True, separators=(",", ":"))
    canonical_output = json.dumps(body.output_schema, sort_keys=True, separators=(",", ":"))
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

    log("schema_registered", capability_hash=capability_hash, agent=agent_pubkey)
    return {"capability_hash": capability_hash}


class SellerRegisterRequest(BaseModel):
    capability_hash: str
    price_cu: float
    capacity: int
    callback_url: str | None = None


def _validate_callback_url(url: str) -> str:
    """Validate callback URL is HTTP(S). Returns normalized URL."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="callback_url must be http or https")
    if not parsed.netloc:
        raise HTTPException(status_code=400, detail="callback_url must have a host")
    return url


@app.post("/v1/sellers/register", status_code=201)
async def register_seller(body: SellerRegisterRequest, agent_pubkey: str = Depends(get_auth)):

    if body.price_cu <= 0:
        raise HTTPException(status_code=400, detail="price_cu must be > 0")
    if body.capacity <= 0:
        raise HTTPException(status_code=400, detail="capacity must be > 0")

    callback_url = None
    if body.callback_url is not None:
        callback_url = _validate_callback_url(body.callback_url)
        # Health check: HEAD request must return 2xx
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as hc:
                check = await hc.head(callback_url)
            if check.status_code >= 300:
                raise HTTPException(status_code=400, detail=f"callback_url health check failed: {check.status_code}")
        except httpx.RequestError:
            raise HTTPException(status_code=400, detail="callback_url unreachable")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT capability_hash FROM schemas WHERE capability_hash = ?",
            (body.capability_hash,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="capability_hash not found")

        # Stake = price_cu (seller puts up one-trade-worth as bond)
        stake = body.price_cu

        # Refund any existing stake before re-registration (CU invariant)
        old = conn.execute(
            "SELECT cu_staked FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
            (agent_pubkey, body.capability_hash),
        ).fetchone()
        old_stake = old["cu_staked"] if old else 0

        agent_row = conn.execute(
            "SELECT cu_balance FROM agents WHERE pubkey = ?", (agent_pubkey,)
        ).fetchone()
        effective_balance = (agent_row["cu_balance"] + old_stake) if agent_row else 0
        if agent_row is None or effective_balance < stake:
            raise HTTPException(status_code=400, detail="insufficient CU balance for stake")

        conn.execute(
            "UPDATE agents SET cu_balance = cu_balance + ? - ? WHERE pubkey = ?",
            (old_stake, stake, agent_pubkey),
        )

        now_ns = time.time_ns()
        conn.execute(
            "INSERT OR REPLACE INTO sellers "
            "(agent_pubkey, capability_hash, price_cu, latency_bound_us, capacity, active_calls, cu_staked, callback_url, sla_set_at_ns, registered_at_ns) "
            "VALUES (?, ?, ?, 0, ?, 0, ?, ?, NULL, ?)",
            (agent_pubkey, body.capability_hash, body.price_cu, body.capacity, stake, callback_url, now_ns),
        )
        record_event(conn, "seller_registered", json.dumps({
            "agent": agent_pubkey,
            "capability_hash": body.capability_hash,
            "price_cu": body.price_cu,
            "cu_staked": stake,
        }))
        conn.commit()
    finally:
        conn.close()

    seller = {
        "agent_pubkey": agent_pubkey,
        "capability_hash": body.capability_hash,
        "price_cu": body.price_cu,
        "latency_bound_us": 0,
        "capacity": body.capacity,
        "active_calls": 0,
        "cu_staked": stake,
    }
    add_seller(seller)

    log("seller_registered", agent=agent_pubkey, capability_hash=body.capability_hash, price_cu=body.price_cu)
    return {"status": "registered", "capability_hash": body.capability_hash, "price_cu": body.price_cu}


@app.get("/v1/sellers/list")
def list_all_sellers():
    """Public seller list for dashboard."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT agent_pubkey, capability_hash, price_cu, capacity, active_calls FROM sellers ORDER BY price_cu ASC"
        ).fetchall()
    finally:
        conn.close()
    return {"sellers": [dict(r) for r in rows]}


@app.get("/v1/sellers/{capability_hash}")
def list_sellers(capability_hash: str):
    sellers = get_sellers(capability_hash)
    return {
        "capability_hash": capability_hash,
        "sellers": [
            {
                "agent_pubkey": s["agent_pubkey"],
                "price_cu": s["price_cu"],
                "capacity": s["capacity"],
                "active_calls": s["active_calls"],
            }
            for s in sellers
        ],
    }


class MatchRequest(BaseModel):
    capability_hash: str
    max_price_cu: float | None = None
    max_latency_us: int | None = None


@app.post("/v1/match")
async def match(body: MatchRequest, buyer_pubkey: str = Depends(get_auth)):

    seller = match_request(body.capability_hash, body.max_price_cu, body.max_latency_us)
    if seller is None:
        return {"status": "no_match"}

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT cu_balance FROM agents WHERE pubkey = ?", (buyer_pubkey,)
        ).fetchone()
        if row["cu_balance"] < seller["price_cu"]:
            return {"status": "insufficient_cu"}

        trade_id = str(uuid.uuid4())
        now_ns = time.time_ns()

        conn.execute(
            "UPDATE agents SET cu_balance = cu_balance - ? WHERE pubkey = ?",
            (seller["price_cu"], buyer_pubkey),
        )
        conn.execute(
            "INSERT INTO trades (id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, start_ns, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'matched')",
            (trade_id, buyer_pubkey, seller["agent_pubkey"], body.capability_hash, seller["price_cu"], now_ns),
        )
        conn.execute(
            "INSERT INTO escrow (trade_id, buyer_pubkey, seller_pubkey, cu_amount, status) "
            "VALUES (?, ?, ?, ?, 'held')",
            (trade_id, buyer_pubkey, seller["agent_pubkey"], seller["price_cu"]),
        )
        conn.execute(
            "UPDATE sellers SET active_calls = active_calls + 1 WHERE agent_pubkey = ? AND capability_hash = ?",
            (seller["agent_pubkey"], body.capability_hash),
        )
        record_event(conn, "match_made", json.dumps({
            "trade_id": trade_id,
            "buyer": buyer_pubkey,
            "seller": seller["agent_pubkey"],
            "capability_hash": body.capability_hash,
            "price_cu": seller["price_cu"],
        }))
        conn.commit()
    finally:
        conn.close()

    increment_active_calls(seller["agent_pubkey"], body.capability_hash)

    log("match_made", trade_id=trade_id, buyer=buyer_pubkey, seller=seller["agent_pubkey"], price_cu=seller["price_cu"])
    return {
        "trade_id": trade_id,
        "seller_pubkey": seller["agent_pubkey"],
        "price_cu": seller["price_cu"],
        "status": "matched",
    }


class ExecuteRequest(BaseModel):
    input: str


@app.post("/v1/trades/{trade_id}/execute")
async def execute_trade(trade_id: str, body: ExecuteRequest, caller_pubkey: str = Depends(get_auth)):

    conn = get_connection()
    try:
        trade = conn.execute(
            "SELECT buyer_pubkey, seller_pubkey, capability_hash, price_cu, status "
            "FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        if trade is None:
            raise HTTPException(status_code=404, detail="trade not found")
        if trade["buyer_pubkey"] != caller_pubkey:
            raise HTTPException(status_code=403, detail="not the buyer of this trade")
        if trade["status"] != "matched":
            raise HTTPException(status_code=400, detail="trade not in matched status")

        # Look up seller callback_url
        seller_row = conn.execute(
            "SELECT callback_url, latency_bound_us FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
            (trade["seller_pubkey"], trade["capability_hash"]),
        ).fetchone()
        callback_url = seller_row["callback_url"] if seller_row else None

        start_ns = time.time_ns()

        if callback_url:
            # Real HTTP callback to seller endpoint
            timeout_us = min((seller_row["latency_bound_us"] or 30_000_000) * 2, 30_000_000)
            timeout_sec = timeout_us / 1_000_000
            import httpx
            try:
                async with httpx.AsyncClient(timeout=timeout_sec) as hc:
                    cb_resp = await hc.post(
                        callback_url,
                        json={"input": body.input, "trade_id": trade_id, "capability_hash": trade["capability_hash"]},
                        headers={"X-Trade-Id": trade_id, "X-Capability-Hash": trade["capability_hash"]},
                    )
                if cb_resp.status_code >= 300:
                    raise httpx.RequestError(f"seller returned {cb_resp.status_code}")
                cb_data = cb_resp.json()
                output_data = cb_data.get("output", "")
            except (httpx.RequestError, httpx.TimeoutException, ValueError, KeyError):
                # Seller failed — trade fails, escrow refunded, bond slashed
                end_ns = time.time_ns()
                latency_us = (end_ns - start_ns) // 1000
                conn.execute(
                    "UPDATE trades SET start_ns = ?, end_ns = ?, latency_us = ?, status = 'failed' WHERE id = ?",
                    (start_ns, end_ns, latency_us, trade_id),
                )
                conn.execute(
                    "UPDATE sellers SET active_calls = MAX(0, active_calls - 1) WHERE agent_pubkey = ? AND capability_hash = ?",
                    (trade["seller_pubkey"], trade["capability_hash"]),
                )
                # Slash seller bond (includes buyer refund + escrow refund)
                seller_full = conn.execute(
                    "SELECT agent_pubkey, capability_hash, latency_bound_us, cu_staked FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
                    (trade["seller_pubkey"], trade["capability_hash"]),
                ).fetchone()
                if seller_full:
                    slash_bond(conn, dict(trade) | {"id": trade_id, "latency_us": latency_us}, dict(seller_full), "callback_failed")
                    # slash_bond sets status='violated'; callback failure is 'failed'
                    conn.execute("UPDATE trades SET status = 'failed' WHERE id = ?", (trade_id,))
                else:
                    # No seller record — still refund buyer
                    conn.execute(
                        "UPDATE agents SET cu_balance = cu_balance + ? WHERE pubkey = ?",
                        (trade["price_cu"], trade["buyer_pubkey"]),
                    )
                    conn.execute(
                        "UPDATE escrow SET status = 'refunded' WHERE trade_id = ?",
                        (trade_id,),
                    )
                record_event(conn, "trade_failed", json.dumps({
                    "trade_id": trade_id, "reason": "callback_failed",
                }))
                conn.commit()
                conn.close()
                decrement_active_calls(trade["seller_pubkey"], trade["capability_hash"])
                return {"status": "failed", "reason": "callback_failed", "latency_us": latency_us}
        else:
            # Legacy simulated execution (no callback_url)
            output_data = f"executed:{body.input}"

        end_ns = time.time_ns()
        latency_us = (end_ns - start_ns) // 1000

        conn.execute(
            "UPDATE trades SET start_ns = ?, end_ns = ?, latency_us = ?, status = 'executed' "
            "WHERE id = ?",
            (start_ns, end_ns, latency_us, trade_id),
        )
        conn.execute(
            "UPDATE sellers SET active_calls = MAX(0, active_calls - 1) "
            "WHERE agent_pubkey = ? AND capability_hash = ?",
            (trade["seller_pubkey"], trade["capability_hash"]),
        )
        record_event(conn, "trade_executed", json.dumps({
            "trade_id": trade_id,
            "buyer": caller_pubkey,
            "seller": trade["seller_pubkey"],
            "latency_us": latency_us,
        }))
        conn.commit()
    finally:
        conn.close()

    decrement_active_calls(trade["seller_pubkey"], trade["capability_hash"])

    log("trade_executed", trade_id=trade_id, latency_us=latency_us)
    return {
        "output": output_data,
        "latency_us": latency_us,
        "status": "executed",
    }


@app.post("/v1/trades/{trade_id}/settle")
async def settle(trade_id: str, caller_pubkey: str = Depends(get_auth)):

    conn = get_connection()
    try:
        trade = conn.execute(
            "SELECT id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, "
            "latency_us, status FROM trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        if trade is None:
            raise HTTPException(status_code=404, detail="trade not found")
        if trade["buyer_pubkey"] != caller_pubkey:
            raise HTTPException(status_code=403, detail="not the buyer of this trade")
        if trade["status"] != "executed":
            raise HTTPException(status_code=400, detail="trade not in executed status")

        seller = conn.execute(
            "SELECT agent_pubkey, capability_hash, latency_bound_us, cu_staked "
            "FROM sellers WHERE agent_pubkey = ? AND capability_hash = ?",
            (trade["seller_pubkey"], trade["capability_hash"]),
        ).fetchone()

        # Verification — output from execute is not stored, so we check latency only
        # (output was already returned to buyer; MVP verifies latency + non-empty)
        passed, reason = verify_trade(
            dict(trade), dict(seller) if seller else {"latency_bound_us": 0, "cu_staked": 0.0}, "output_present"
        )

        if passed:
            seller_receives, fee_cu = settle_trade(conn, dict(trade))
            check_sla_decoherence(conn, trade["seller_pubkey"], trade["capability_hash"])
            maybe_set_sla(conn, trade["seller_pubkey"], trade["capability_hash"])
            conn.commit()
            return {
                "status": "completed",
                "seller_receives": seller_receives,
                "fee_cu": fee_cu,
            }
        else:
            slash_bond(conn, dict(trade), dict(seller) if seller else {"cu_staked": 0.0}, reason)
            conn.commit()
            return {
                "status": "violated",
                "reason": reason,
            }
    finally:
        conn.close()


@app.get("/v1/events/stream")
def stream_events(since: int = 0, limit: int = 200):
    """Public event stream for live dashboard. Returns events since seq > since."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT seq, event_type, event_data, timestamp_ns FROM events WHERE seq > ? ORDER BY seq ASC LIMIT ?",
            (since, limit),
        ).fetchall()
    finally:
        conn.close()
    return {"events": [dict(r) for r in rows]}


@app.get("/v1/events/{agent_id}")
async def get_events(agent_id: str, event_type: str | None = None, limit: int = 100, caller_pubkey: str = Depends(get_auth)):

    conn = get_connection()
    try:
        row = conn.execute("SELECT pubkey FROM agents WHERE pubkey = ?", (agent_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="agent not found")
        events = query_events(conn, agent_id, event_type=event_type, limit=limit)
    finally:
        conn.close()
    return {"agent_id": agent_id, "events": events}


# ── Visualization endpoints (public, no auth) ───────────

@app.get("/v1/stats")
def get_stats():
    """System-wide stats for dashboard."""
    conn = get_connection()
    try:
        total_trades = conn.execute("SELECT COUNT(*) as c FROM trades").fetchone()["c"]
        completed_trades = conn.execute("SELECT COUNT(*) as c FROM trades WHERE status = 'completed'").fetchone()["c"]
        active_agents = conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
        active_sellers = conn.execute("SELECT COUNT(*) as c FROM sellers").fetchone()["c"]
        total_cu = conn.execute("SELECT COALESCE(SUM(cu_balance), 0) as s FROM agents").fetchone()["s"]
        escrow_held = conn.execute("SELECT COALESCE(SUM(cu_amount), 0) as s FROM escrow WHERE status = 'held'").fetchone()["s"]
        fees_earned = conn.execute(
            "SELECT COALESCE(SUM(price_cu * 0.015), 0) as s FROM trades WHERE status = 'completed'"
        ).fetchone()["s"]
    finally:
        conn.close()
    return {
        "total_trades": total_trades,
        "completed_trades": completed_trades,
        "active_agents": active_agents,
        "active_sellers": active_sellers,
        "total_cu": round(total_cu, 4),
        "escrow_held": round(escrow_held, 4),
        "fees_earned": round(fees_earned, 4),
    }


@app.get("/v1/agents/list")
def list_agents():
    """Public agent list for dashboard (no api_keys exposed)."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT pubkey, cu_balance FROM agents ORDER BY cu_balance DESC").fetchall()
    finally:
        conn.close()
    return {"agents": [{"pubkey": r["pubkey"], "cu_balance": round(r["cu_balance"], 4)} for r in rows]}


@app.get("/v1/trades/recent")
def recent_trades(limit: int = 50):
    """Recent trades with output data for visualization."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, buyer_pubkey, seller_pubkey, capability_hash, price_cu, status, latency_us "
            "FROM trades ORDER BY start_ns DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return {"trades": [dict(r) for r in rows]}


# ── Market control (start/stop auto-trader) ────────────

_trader_proc = None  # subprocess.Popen | None


@app.get("/v1/market/status")
def market_status():
    """Check if the auto-trader process is running."""
    global _trader_proc
    if _trader_proc is not None and _trader_proc.poll() is None:
        return {"running": True, "pid": _trader_proc.pid}
    _trader_proc = None
    return {"running": False}


@app.post("/v1/market/start")
def market_start():
    """Start the auto-trader as a background subprocess."""
    global _trader_proc
    if _trader_proc is not None and _trader_proc.poll() is None:
        return {"status": "already_running", "pid": _trader_proc.pid}
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_trader.py")
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_trader.log")
    log_fh = open(log_file, "a")
    _trader_proc = subprocess.Popen(
        [sys.executable, "-u", script],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=log_fh,
        stderr=log_fh,
    )
    return {"status": "started", "pid": _trader_proc.pid}


@app.post("/v1/market/stop")
def market_stop():
    """Stop the auto-trader subprocess."""
    global _trader_proc
    if _trader_proc is None or _trader_proc.poll() is not None:
        _trader_proc = None
        return {"status": "not_running"}
    _trader_proc.send_signal(signal.SIGTERM)
    try:
        _trader_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _trader_proc.kill()
    _trader_proc = None
    return {"status": "stopped"}


@app.get("/v1/trade_log")
def trade_log():
    """Returns the auto-trader trade log with Ollama outputs."""
    log_path = os.path.join(os.path.dirname(__file__), "trade_log.json")
    if not os.path.exists(log_path):
        return {"trades": []}
    with open(log_path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = []
    return {"trades": data}


# ── Faucet ──────────────────────────────────────────────

@app.post("/v1/faucet")
async def faucet(agent_pubkey: str = Depends(get_auth)):
    """Drip free CU to the calling agent.

    First call ever: credits FAUCET_FIRST_CU (500 CU).
    Subsequent calls: credits FAUCET_DRIP_CU (50 CU) once per 24 h.
    Lifetime cap: FAUCET_MAX_CU (1000 CU).
    """
    if not os.environ.get("FAUCET_ENABLED", "1"):
        raise HTTPException(status_code=503, detail="faucet disabled")

    now_ns = time.time_ns()
    conn = get_connection()
    try:
        # Ensure agent exists
        agent_row = conn.execute(
            "SELECT cu_balance FROM agents WHERE pubkey = ?", (agent_pubkey,)
        ).fetchone()
        if agent_row is None:
            raise HTTPException(status_code=404, detail="agent not found")

        # Load or init faucet state
        state = conn.execute(
            "SELECT total_credited_cu, last_drip_ns FROM faucet_state WHERE agent_pubkey = ?",
            (agent_pubkey,),
        ).fetchone()

        if state is None:
            # First ever call
            credit = FAUCET_FIRST_CU
            new_total = credit
            conn.execute(
                "INSERT INTO faucet_state (agent_pubkey, total_credited_cu, last_drip_ns) VALUES (?, ?, ?)",
                (agent_pubkey, new_total, now_ns),
            )
        else:
            total_so_far = state["total_credited_cu"]
            last_drip_ns = state["last_drip_ns"]

            if total_so_far >= FAUCET_MAX_CU:
                return {
                    "credited": 0.0,
                    "balance": round(agent_row["cu_balance"], 4),
                    "message": "lifetime cap reached",
                    "next_drip_at": None,
                }

            if last_drip_ns is not None and (now_ns - last_drip_ns) < FAUCET_WINDOW_NS:
                next_drip_ns = last_drip_ns + FAUCET_WINDOW_NS
                return {
                    "credited": 0.0,
                    "balance": round(agent_row["cu_balance"], 4),
                    "message": "too soon — wait 24h between drips",
                    "next_drip_at": next_drip_ns,
                }

            remaining_cap = FAUCET_MAX_CU - total_so_far
            credit = min(FAUCET_DRIP_CU, remaining_cap)
            new_total = total_so_far + credit
            conn.execute(
                "UPDATE faucet_state SET total_credited_cu = ?, last_drip_ns = ? WHERE agent_pubkey = ?",
                (new_total, now_ns, agent_pubkey),
            )

        conn.execute(
            "UPDATE agents SET cu_balance = cu_balance + ? WHERE pubkey = ?",
            (credit, agent_pubkey),
        )
        new_balance = agent_row["cu_balance"] + credit
        record_event(conn, "faucet_drip", json.dumps({
            "agent": agent_pubkey, "credited": credit, "total_from_faucet": new_total,
        }))
        conn.commit()
    finally:
        conn.close()

    log("faucet_drip", agent=agent_pubkey, credited=credit)
    next_drip_ns = now_ns + FAUCET_WINDOW_NS if new_total < FAUCET_MAX_CU else None
    return {
        "credited": credit,
        "balance": round(new_balance, 4),
        "total_from_faucet": new_total,
        "next_drip_at": next_drip_ns,
    }


# ── Leaderboard ─────────────────────────────────────────

@app.get("/v1/leaderboard")
def leaderboard(limit: int = 20):
    """Public leaderboard: top sellers by CU earned, trade count, and SLA compliance.

    No authentication required — machine-readable JSON suitable for LLM consumption.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT
                s.agent_pubkey,
                s.capability_hash,
                s.price_cu,
                s.cu_staked,
                s.latency_bound_us,
                COUNT(t.id)                                      AS trade_count,
                COALESCE(SUM(CASE WHEN t.status = 'completed'
                               THEN t.price_cu * (1 - 0.015) END), 0) AS cu_earned,
                COALESCE(SUM(CASE WHEN t.status = 'completed' THEN 1 ELSE 0 END), 0) AS completed,
                COALESCE(SUM(CASE WHEN t.status = 'violated'  THEN 1 ELSE 0 END), 0) AS violations
            FROM sellers s
            LEFT JOIN trades t
                   ON t.seller_pubkey = s.agent_pubkey
                  AND t.capability_hash = s.capability_hash
            GROUP BY s.agent_pubkey, s.capability_hash
            ORDER BY cu_earned DESC, trade_count DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    entries = []
    for r in rows:
        total   = r["trade_count"] or 0
        done    = r["completed"]   or 0
        viols   = r["violations"]  or 0
        sla_pct = round(100.0 * done / total, 1) if total > 0 else None
        verified = done >= 10 and viols == 0 and total >= 10
        entries.append({
            "agent_pubkey":     r["agent_pubkey"],
            "capability_hash":  r["capability_hash"],
            "price_cu":         r["price_cu"],
            "cu_earned":        round(r["cu_earned"], 4),
            "trade_count":      total,
            "sla_pct":          sla_pct,
            "verified_seller":  verified,
        })

    return {"leaderboard": entries, "limit": limit}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
