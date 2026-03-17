# ollama_client.py — Thin wrapper around Ollama HTTP API
import json
import urllib.request
import base64

OLLAMA_URL = "http://localhost:11434"


def generate(model, prompt, timeout=300):
    """Generate text from a prompt. Returns the response string."""
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    return result["response"]


def generate_with_image(model, prompt, image_bytes, timeout=300):
    """Generate text from a prompt + image. Returns the response string."""
    b64_image = base64.b64encode(image_bytes).decode()
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [b64_image],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    return result["response"]
