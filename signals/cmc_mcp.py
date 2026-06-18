"""CMC Agent Hub MCP client — for the "Best Use of Agent Hub" special prize.

Talks to the CoinMarketCap Agent Hub MCP server (Streamable-HTTP JSON-RPC) instead of
the classic Pro REST API, so the agent genuinely consumes the Agent Hub every cycle.

Endpoint + auth (verified 2026-06-18 from the official docs):
    https://mcp.coinmarketcap.com/mcp   header: X-CMC-MCP-API-KEY: <CMC_API_KEY>

The 12 CMC MCP tools are runtime-discovered. Tool names below are best-effort from the
docs — run `python -m signals.cmc_mcp` (with CMC_API_KEY set) to print the live
tools/list and confirm/adjust the TOOL_* constants if they differ.

cmc.py uses this when CMC_TRANSPORT=mcp, and falls back to the REST path on any error,
so the live loop is never broken by an MCP hiccup.
"""

from __future__ import annotations

import json
import os
import logging

import requests

log = logging.getLogger("conviction.cmc_mcp")

MCP_URL = os.getenv("CMC_MCP_URL", "https://mcp.coinmarketcap.com/mcp")

# Verified against the live tools/list (2026-06-18).
TOOL_GLOBAL = os.getenv("CMC_TOOL_GLOBAL", "get_global_metrics_latest")        # Fear & Greed, dominance
TOOL_QUOTES = os.getenv("CMC_TOOL_QUOTES", "get_crypto_quotes_latest")         # price/volume per symbol
TOOL_DERIV = os.getenv("CMC_TOOL_DERIVATIVES", "get_global_crypto_derivatives_metrics")  # funding rates

_id = 0


def _key() -> str | None:
    return os.getenv("CMC_API_KEY")


def _rpc(method: str, params: dict | None = None) -> dict:
    """One JSON-RPC call over MCP Streamable HTTP. Handles json or SSE responses."""
    global _id
    _id += 1
    key = _key()
    if not key:
        raise RuntimeError("CMC_API_KEY not set")
    headers = {
        "X-CMC-MCP-API-KEY": key,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    body = {"jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}}
    r = requests.post(MCP_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        # parse SSE: last `data:` line holds the JSON-RPC envelope
        payload = None
        for line in r.text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
        data = json.loads(payload) if payload else {}
    else:
        data = r.json()
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})


def list_tools() -> list[dict]:
    """tools/list — the live tool catalog (names + input schemas)."""
    return _rpc("tools/list").get("tools", [])


def call_tool(name: str, arguments: dict | None = None) -> dict:
    """tools/call — invoke a tool, return its structured/text content as a dict.

    Raises on a CMC error payload (e.g. {"error":{"code":1001,"message":"...invalid"}})
    so callers fall back cleanly instead of treating the error as data.
    """
    res = _rpc("tools/call", {"name": name, "arguments": arguments or {}})
    out: dict = {}
    for block in res.get("content", []):
        if block.get("type") == "text":
            try:
                out = json.loads(block["text"])
            except Exception:
                out = {"text": block["text"]}
            break
        if block.get("type") == "json":
            out = block.get("json", {})
            break
    else:
        out = res.get("structuredContent", res)
    if isinstance(out, dict) and isinstance(out.get("error"), dict):
        raise RuntimeError(f"CMC tool error: {out['error']}")
    return out


def discover() -> None:
    """CLI: print the live tools so the TOOL_* constants can be confirmed."""
    for t in list_tools():
        print(f"- {t.get('name')}: {t.get('description', '')[:80]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover()
