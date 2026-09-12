"""Entry point: verify config, open Telegram, run the webhook server."""

from __future__ import annotations

import asyncio
import logging
import signal

import aiohttp
from aiohttp import web

from .alerts import Alerter
from .authors import SyncSummary
from .config import Config
from .forge import ForgeClient
from .handler import Handler
from .state import State
from .telegram import Telegram
from .webhook import build_app

log = logging.getLogger("gitbot")


async def run() -> None:
    cfg = Config.from_env()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    state = State.load(cfg.state_file)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    async with (
        Telegram(cfg.bot_token, cfg.chat_id, cfg.message_thread_id) as tg,
        aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as forge_session,
    ):
        me = await tg.me()
        log.info(
            "bot @%s posting to chat %s%s",
            me.get("username"),
            cfg.chat_id,
            f" thread {cfg.message_thread_id}" if cfg.message_thread_id else "",
        )
        alerter = Alerter(tg.send_to, cfg.admin_chat_id)
        tg.alerter = alerter
        summary = SyncSummary(forge_session, cfg.forge_base)
        forge = ForgeClient(forge_session, cfg.forge_base)
        handler = Handler(cfg, tg, state, summary, forge)
        app = build_app(cfg, handler, state, alerter)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, cfg.listen_host, cfg.listen_port)
        await site.start()
        log.info("listening on http://%s:%d%s", cfg.listen_host, cfg.listen_port, cfg.webhook_path)
        try:
            await stop.wait()
        finally:
            handler.batcher.flush_all()
            await runner.cleanup()
            state.save(cfg.state_file)
            log.info("stopped")


def cli() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
