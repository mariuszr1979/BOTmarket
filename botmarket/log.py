# log.py — Structured JSON logging to stdout
import json
import time
import sys


def log(event, **kw):
    """Emit one structured JSON log line to stdout."""
    entry = {"ts": time.time(), "event": event}
    entry.update(kw)
    sys.stdout.write(json.dumps(entry, default=str) + "\n")
    sys.stdout.flush()
