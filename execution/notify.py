"""Telegram notifier — stream the agent's decisions + trades to a bot chat.

Fail-safe: disabled unless TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set; any error is
swallowed (a notifier outage must never affect trading). HTML parse mode.
"""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger("conviction.notify")
TIMEOUT = 10
_API = "https://api.telegram.org/bot{token}/sendMessage"


def enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send(text: str) -> bool:
    """Post a message to the configured chat. Returns True on success, never raises."""
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        r = requests.post(_API.format(token=token),
                          json={"chat_id": chat, "text": text, "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=TIMEOUT)
        if not r.ok:
            log.warning("telegram send %s: %s", r.status_code, r.text[:120])
        return r.ok
    except Exception as e:                       # never let notification break the loop
        log.warning("telegram send failed: %s", e)
        return False
