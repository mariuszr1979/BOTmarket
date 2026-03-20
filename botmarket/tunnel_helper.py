#!/usr/bin/env python3
"""tunnel_helper.py — Start a Cloudflare Tunnel and return the public HTTPS URL.

Supports cloudflared (Cloudflare Tunnel). If cloudflared is not installed,
offers to download and install it automatically.

Usage:
    from tunnel_helper import start_tunnel
    url = start_tunnel(port=8001)   # blocks until tunnel URL is available
    print(url)   # => "https://xxxx.trycloudflare.com"

Or run standalone:
    python tunnel_helper.py 8001
"""
import logging
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request

log = logging.getLogger("tunnel_helper")

_CLOUDFLARED_INSTALL_URLS = {
    # (system, machine) → download URL
    ("Linux",  "x86_64"):  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
    ("Linux",  "aarch64"): "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    ("Darwin", "x86_64"):  "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz",
    ("Darwin", "arm64"):   "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64.tgz",
}

_CLOUDFLARED_TIMEOUT = 45   # seconds to wait for tunnel URL


def _find_cloudflared() -> str | None:
    """Return path to cloudflared if it's on PATH or in ~/.local/bin."""
    import shutil
    found = shutil.which("cloudflared")
    if found:
        return found
    local = os.path.expanduser("~/.local/bin/cloudflared")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return None


def _install_cloudflared() -> str:
    """Download cloudflared binary to ~/.local/bin/cloudflared. Returns path."""
    system  = platform.system()
    machine = platform.machine()
    url = _CLOUDFLARED_INSTALL_URLS.get((system, machine))

    if url is None:
        raise RuntimeError(
            f"No auto-install for cloudflared on {system}/{machine}. "
            "Install manually: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
        )

    dest_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "cloudflared")

    log.info("downloading cloudflared from %s ...", url)

    if url.endswith(".tgz"):
        import tarfile, io
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            member = next(m for m in tf.getmembers() if "cloudflared" in m.name and not m.name.endswith("/"))
            f = tf.extractfile(member)
            with open(dest, "wb") as out:
                out.write(f.read())
    else:
        with urllib.request.urlopen(url, timeout=120) as resp:
            with open(dest, "wb") as out:
                out.write(resp.read())

    os.chmod(dest, 0o755)
    log.info("cloudflared installed at %s", dest)
    return dest


def start_tunnel(port: int, timeout: int = _CLOUDFLARED_TIMEOUT) -> str:
    """Start a Cloudflare Quick Tunnel for localhost:port.

    Returns the public HTTPS URL once it's ready.
    Raises RuntimeError if the tunnel can't be started within `timeout` seconds.
    """
    binary = _find_cloudflared()
    if binary is None:
        log.info("cloudflared not found — installing ...")
        binary = _install_cloudflared()

    url_queue: queue.Queue = queue.Queue()
    proc_holder: list[subprocess.Popen] = []

    def _reader():
        proc = subprocess.Popen(
            [binary, "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        proc_holder.append(proc)
        for line in proc.stdout:
            line = line.strip()
            if line:
                log.debug("cloudflared: %s", line)
            m = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if m:
                url_queue.put(m.group(0))
                return
            # Some versions print via the INF log prefix
            m2 = re.search(r"https://[a-zA-Z0-9\-]+\.cloudflare-tunnel\.com", line)
            if m2:
                url_queue.put(m2.group(0))
                return

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    try:
        tunnel_url = url_queue.get(timeout=timeout)
    except queue.Empty:
        raise RuntimeError(
            f"Cloudflare Tunnel URL not received within {timeout}s. "
            "Check cloudflared output."
        )

    log.info("tunnel ready: %s → localhost:%d", tunnel_url, port)
    return tunnel_url


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    url = start_tunnel(port)
    print(url)
