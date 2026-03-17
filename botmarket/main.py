from contextlib import asynccontextmanager
from fastapi import FastAPI
from db import init_db


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="BOTmarket", version="0.1.0", lifespan=lifespan)


@app.get("/v1/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
