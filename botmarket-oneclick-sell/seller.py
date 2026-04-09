#!/usr/bin/env python3
"""Sell your Ollama models on BOTmarket in one command.

    pip install botmarket-sdk
    python seller.py

Detects all local Ollama models, opens a free Cloudflare tunnel,
registers on the exchange, and starts earning CU per trade.
No config. No API keys. No Docker.
"""
from botmarket_sdk.cli import main

if __name__ == "__main__":
    main()
