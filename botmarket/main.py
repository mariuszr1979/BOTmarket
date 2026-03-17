from contextlib import asynccontextmanager
import json
import secrets
import uuid
import time

from fastapi import FastAPI
from db import init_db, get_connection
from events import record_event


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="BOTmarket", version="0.1.0", lifespan=lifespan)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
