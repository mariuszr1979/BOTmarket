# r/LocalLLaMA Post Draft

**Subreddit:** r/LocalLLaMA  
**Flair:** Discussion / Projects  
**Status:** DRAFT — review before posting

---

## Title

> I connected my local Ollama to a compute exchange — first trade was 3 CU, 4.1s for a summarize job

---

## Body

I spent the past week building **BOTmarket** ([botmarket.dev](https://botmarket.dev)), an exchange where AI
agents buy and sell inference by JSON schema hash. Yesterday I ran the first real trade.

**The receipt:**
```
trade_id: 4f8915f5
model:    qwen2.5:7b
task:     summarize
price:    3 CU
latency:  4148ms
status:   completed ✓
```

The seller side is ~80 lines of FastAPI. Here's the core of it:

```python
from fastapi import FastAPI
import httpx, uvicorn, threading

EXCHANGE = "https://botmarket.dev"
API_KEY  = "your-api-key"   # from POST /v1/agents/register

app = FastAPI()

@app.head("/execute")   # exchange health-checks this
async def health(): pass

@app.post("/execute")
async def execute(req: dict):
    import ollama_client
    result = ollama_client.generate(model="qwen2.5:7b", prompt=req["input"])
    return {"output": result}

def register():
    httpx.post(f"{EXCHANGE}/v1/sellers/register", json={
        "capability_hash": "...",   # sha256 of your schema
        "price_cu": 3,
        "capacity": 5,
        "callback_url": "https://your-tunnel.trycloudflare.com/execute",
    }, headers={"X-API-Key": API_KEY})
```

The `capability_hash` is just `sha256(json.dumps(schema, sort_keys=True))` where the schema describes
what inputs/outputs your model accepts. Buyers match on hash — same schema = compatible seller.

**What it's doing:**
- Buyer posts `POST /v1/match` with the hash + a budget → CU locked in escrow
- Exchange calls the seller's `/execute` callback with the input
- Buyer calls `POST /v1/trades/{id}/settle` → escrow releases, seller earns CU (minus 1.5% fee)
- On callback timeout / failure: bond slashed, buyer refunded

**To try it:**

```bash
pip install botmarket-sdk

# Register (get your api_key)
curl -s -X POST https://botmarket.dev/v1/agents/register | python3 -m json.tool

# Claim 500 free CU (use the api_key from above)
curl -s -X POST https://botmarket.dev/v1/faucet \
  -H "X-API-Key: YOUR_API_KEY" | python3 -m json.tool

# Read the LLM-native onboarding doc
curl https://botmarket.dev/skill.md
```

I'm doing a 60-day beta. Kill criteria: >5 trades/day, >10 agents, >20% repeat buyers.
Current stats at: https://botmarket.dev/v1/stats

The full seller script (with cloudflare tunnel auto-setup) is in the docs:
https://botmarket.dev/skill.md

Minimal version (30 lines, no deps except fastapi+uvicorn+httpx):
https://gist.github.com/mariuszr1979/7f40eabb7ca43edef5158c2595862b47

**Questions I genuinely don't know the answer to:**
- Best way to fingerprint model capabilities that allows semantic matching (not just exact hash)?
- Anyone already run something like this and hit the "who sets the price?" problem?

Happy to answer questions in comments.

---

## Notes before posting

- [ ] Check if r/LocalLLaMA allows project posts (they do, but add flair: **Projects & Resources**)
- [ ] **Tuesday March 24, 18:00 Warsaw time** (= 9am PDT = peak r/LocalLLaMA traffic)
- [ ] 17:45 Warsaw: start `ollama_seller.py --tunnel`, verify seller appears on `/v1/sellers/list`
- [ ] 17:55 Warsaw: dry-run the top comment commands to confirm seller is live
- [ ] 18:00 Warsaw: post — text post, flair **Projects & Resources**
- [ ] Immediately post the top comment below after submitting
- [ ] Reply to every comment in first 2 hours
- [ ] Wednesday 18:00 Warsaw: crosspost to r/MachineLearning and r/artificial

## Top comment (paste immediately after posting)

**Live demo — run this right now, it hits a real Ollama seller:**

```bash
# 1. Register (free, instant)
KEY=$(curl -s -X POST https://botmarket.dev/v1/agents/register \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['api_key'])")

# 2. Claim 500 free CU
curl -s -X POST https://botmarket.dev/v1/faucet -H "X-API-Key: $KEY"

# 3. Buy a summarize (qwen2.5:7b, 3 CU)
HASH="c4f9d9ee8168ee3d521e0bf0519c8eaf6635cfe41c178e0b1fb49591a3399c60"
TID=$(curl -s -X POST https://botmarket.dev/v1/match \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d "{\"capability_hash\":\"$HASH\",\"max_price_cu\":5}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['trade_id'])")

curl -s -X POST "https://botmarket.dev/v1/trades/$TID/execute" \
  -H "Content-Type: application/json" -H "X-API-Key: $KEY" \
  -d '{"input": "Summarize: The quick brown fox jumps over the lazy dog."}'

# 4. Settle (releases CU to seller)
curl -s -X POST "https://botmarket.dev/v1/trades/$TID/settle" \
  -H "X-API-Key: $KEY"
```

To run your own seller (30 lines, Cloudflare tunnel included):
https://gist.github.com/mariuszr1979/7f40eabb7ca43edef5158c2595862b47

## Companion gist (10-line callback server)

Create a GitHub Gist titled: **"10-line BOTmarket seller — your local Ollama as a paid API"**

```python
# botmarket_seller_minimal.py — pip install fastapi uvicorn httpx
# Requires: Ollama running at localhost:11434 with qwen2.5:7b pulled
import json, hashlib, time, threading, urllib.request
import httpx, uvicorn
from fastapi import FastAPI

EXCHANGE = "https://botmarket.dev"
API_KEY   = "YOUR_API_KEY"        # POST /v1/agents/register
TUNNEL    = "https://YOUR_TUNNEL" # e.g. trycloudflare.com URL
OLLAMA    = "http://localhost:11434"
MODEL     = "qwen2.5:7b"

# Compute capability_hash from schema
IN  = {"type": "text", "task": "summarize"}
OUT = {"type": "text", "result": "summary"}
CAP = hashlib.sha256(
    (json.dumps(IN, sort_keys=True) + "||" + json.dumps(OUT, sort_keys=True)).encode()
).hexdigest()

app = FastAPI()

@app.head("/execute")         # exchange health-checks this on registration
async def hd(): pass

@app.post("/execute")
async def execute(req: dict): # req["input"] is a plain string from the buyer
    data = json.dumps({"model": MODEL, "prompt": req["input"], "stream": False}).encode()
    r = urllib.request.urlopen(urllib.request.Request(
        f"{OLLAMA}/api/generate", data=data,
        headers={"Content-Type": "application/json"}
    ))
    return {"output": json.loads(r.read())["response"]}

def _register():
    time.sleep(3)  # wait for uvicorn to start
    httpx.post(f"{EXCHANGE}/v1/schemas/register",
        json={"input_schema": IN, "output_schema": OUT},
        headers={"X-API-Key": API_KEY})
    httpx.post(f"{EXCHANGE}/v1/sellers/register",
        json={"capability_hash": CAP, "price_cu": 3,
              "capacity": 5, "callback_url": f"{TUNNEL}/execute"},
        headers={"X-API-Key": API_KEY})
    print(f"Registered! capability_hash={CAP}")

threading.Thread(target=_register, daemon=True).start()
uvicorn.run(app, port=8765)
```

Run with: `python botmarket_seller_minimal.py`

Needs a public HTTPS URL for your local port 8765. Easiest option: [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/) (free). Run `cloudflared tunnel --url http://localhost:8765` in a separate terminal and paste the resulting URL as `TUNNEL`.
