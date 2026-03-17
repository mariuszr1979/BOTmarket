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


@asynccontextmanager
async def lifespan(app):
    init_db()
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
