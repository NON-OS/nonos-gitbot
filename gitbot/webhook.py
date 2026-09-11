"""The Forgejo webhook receiver.

Verifies the HMAC over the raw request body before parsing anything, drops
duplicate and unsigned deliveries, answers fast, and hands verified events
to the handler. Payloads are never logged; only the delivery id is.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from aiohttp import web

from .config import Config
from .handler import Handler
from .state import State

log = logging.getLogger("gitbot.webhook")

ACCEPTED_EVENTS = {"push", "pull_request", "release"}


def _header(request: web.Request, name: str) -> str:
    return request.headers.get(f"X-Forgejo-{name}") or request.headers.get(f"X-Gitea-{name}") or ""


def verify(secret: bytes, raw_body: bytes, signature: str) -> bool:
    want = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, signature or "")


class Webhook:
    def __init__(self, cfg: Config, handler: Handler, state: State):
        self.cfg = cfg
        self.handler = handler
        self.state = state
        self._secret = cfg.webhook_secret.encode()

    async def handle(self, request: web.Request) -> web.Response:
        delivery = _header(request, "Delivery")
        event = _header(request, "Event")
        raw = await request.read()

        if not verify(self._secret, raw, _header(request, "Signature")):
            log.warning("rejected delivery %s: bad signature", delivery or "?")
            return web.Response(status=401)

        if event not in ACCEPTED_EVENTS:
            return web.Response(status=202, text="ignored")

        if self.state.seen(delivery):
            log.info("duplicate delivery %s dropped", delivery)
            return web.Response(status=202, text="duplicate")
        self.state.save(self.cfg.state_file)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            log.warning("delivery %s: body was not valid JSON", delivery or "?")
            return web.Response(status=400)

        try:
            self.handler.dispatch(event, payload)
        except Exception as exc:  # never fail the delivery over a render bug
            log.exception("dispatch failed for delivery %s: %s", delivery or "?", exc)

        return web.Response(status=202, text="ok")

    async def health(self, request: web.Request) -> web.Response:
        return web.Response(text="ok")


def build_app(cfg: Config, handler: Handler, state: State) -> web.Application:
    hook = Webhook(cfg, handler, state)
    app = web.Application()
    app.router.add_post(cfg.webhook_path, hook.handle)
    app.router.add_get("/healthz", hook.health)
    return app
