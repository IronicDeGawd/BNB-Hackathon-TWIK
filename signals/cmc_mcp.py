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

# Best-effort tool names — confirm via discover() (tools/list).
TOOL_GLOBAL = os.getenv("CMC_TOOL_GLOBAL", "get_global_metrics")     # Fear & Greed, dominance
TOOL_QUOTES = os.getenv("CMC_TOOL_QUOTES", "get_crypto_quotes_latest")  # price/volume per symbol
TOOL_DERIV = os.getenv("CMC_TOOL_DERIVATIVES", "get_derivatives")    # funding rates

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
    """tools/call — invoke a tool, return its structured/text content as a dict."""
    res = _rpc("tools/call", {"name": name, "arguments": arguments or {}})
    # MCP returns content blocks; pull JSON from the first text/json block.
    for block in res.get("content", []):
        if block.get("type") == "text":
            try:
                return json.loads(block["text"])
            except Exception:
                return {"text": block["text"]}
        if block.get("type") == "json":
            return block.get("json", {})
    return res.get("structuredContent", res)


def discover() -> None:
    """CLI: print the live tools so the TOOL_* constants can be confirmed."""
    for t in list_tools():
        print(f"- {t.get('name')}: {t.get('description', '')[:80]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discover()
