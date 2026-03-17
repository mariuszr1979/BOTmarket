from contextlib import asynccontextmanager
import hashlib
import json
import secrets
import uuid
import time

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from db import init_db, get_connection
from events import record_event
from matching import rebuild_seller_tables, add_seller, get_sellers, match_request, increment_active_calls, decrement_active_calls
from verification import verify_trade
from settlement import settle_trade, slash_bond


@asynccontextmanager
async def lifespan(app):
    conn = init_db()
    rebuild_seller_tables(conn)
    conn.close()
    yield


app = FastAPI(title="BOTmarket", version="0.1.0", lifespan=lifespan)


def authenticate(x_api_key: str = Header()):
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


@app.get("/v1/health")
def health():
    return {"status": "ok"}


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

    return {"agent_id": pubkey, "api_key": api_key, "cu_balance": 0.0}


class SchemaRegisterRequest(BaseModel):
    input_schema: dict
    output_schema: dict


@app.post("/v1/schemas/register", status_code=201)
def register_schema(body: SchemaRegisterRequest, x_api_key: str = Header()):
    agent_pubkey = authenticate(x_api_key)

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

    return {"capability_hash": capability_hash}


class SellerRegisterRequest(BaseModel):
    capability_hash: str
    price_cu: float
    capacity: int


@app.post("/v1/sellers/register", status_code=201)
def register_seller(body: SellerRegisterRequest, x_api_key: str = Header()):
    agent_pubkey = authenticate(x_api_key)

    if body.price_cu <= 0:
        raise HTTPException(status_code=400, detail="price_cu must be > 0")
    if body.capacity <= 0:
        raise HTTPException(status_code=400, detail="capacity must be > 0")

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT capability_hash FROM schemas WHERE capability_hash = ?",
            (body.capability_hash,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="capability_hash not found")

        now_ns = time.time_ns()
        conn.execute(
            "INSERT OR REPLACE INTO sellers "
            "(agent_pubkey, capability_hash, price_cu, latency_bound_us, capacity, active_calls, cu_staked, registered_at_ns) "
            "VALUES (?, ?, ?, 0, ?, 0, 0.0, ?)",
            (agent_pubkey, body.capability_hash, body.price_cu, body.capacity, now_ns),
        )
        record_event(conn, "seller_registered", json.dumps({
            "agent": agent_pubkey,
            "capability_hash": body.capability_hash,
            "price_cu": body.price_cu,
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
        "cu_staked": 0.0,
    }
    add_seller(seller)

    return {"status": "registered", "capability_hash": body.capability_hash, "price_cu": body.price_cu}


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
def match(body: MatchRequest, x_api_key: str = Header()):
    buyer_pubkey = authenticate(x_api_key)

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

    return {
        "trade_id": trade_id,
        "seller_pubkey": seller["agent_pubkey"],
        "price_cu": seller["price_cu"],
        "status": "matched",
    }


class ExecuteRequest(BaseModel):
    input: str


@app.post("/v1/trades/{trade_id}/execute")
def execute_trade(trade_id: str, body: ExecuteRequest, x_api_key: str = Header()):
    caller_pubkey = authenticate(x_api_key)

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

        start_ns = time.time_ns()
        # MVP: simulated seller execution — real HTTP callback is Phase 2
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

    return {
        "output": output_data,
        "latency_us": latency_us,
        "status": "executed",
    }


@app.post("/v1/trades/{trade_id}/settle")
def settle(trade_id: str, x_api_key: str = Header()):
    caller_pubkey = authenticate(x_api_key)

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
