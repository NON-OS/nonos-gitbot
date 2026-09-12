"""Send a warning to a private admin chat when something keeps failing, at
most once an hour per fault. Off unless an admin chat is configured. The
admin chat is separate from the group the bot posts to."""

from __future__ import annotations

import logging
import time

log = logging.getLogger("gitbot.alerts")

DEFAULT_COOLDOWN = 3600.0


class Alerter:
    def __init__(self, send, admin_chat_id: int, cooldown: float = DEFAULT_COOLDOWN):
        self._send = send
        self.admin_chat_id = admin_chat_id
        self._cooldown = cooldown
        self._last: dict[str, float] = {}

    async def fault(self, fault: str, detail: str) -> None:
        if not self.admin_chat_id:
            return
        now = time.monotonic()
        if now - self._last.get(fault, -self._cooldown) < self._cooldown:
            return
        self._last[fault] = now
        try:
            await self._send(self.admin_chat_id, f"⚠️ {fault}: {detail}")
        except Exception as exc:  # never let an alert failure raise
            log.warning("could not deliver alert %s: %s", fault, exc)
