"""Telegram Bot API client with a single serialising worker.

Events are posted as a photo with the message as the caption. Each banner is
uploaded once; Telegram returns a file_id and the client sends that from then
on. A pull request stays one message: its image and caption are swapped
together with editMessageMedia as it opens, merges or closes. The webhook
handler answers Forgejo fast and drops jobs here; one worker drains them,
spacing sends so a burst never trips the rate limit, and honouring the retry
delay on 429. The bot token never reaches the log output.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable
from pathlib import Path
from typing import Any, Callable

import aiohttp

log = logging.getLogger("gitbot.tg")

MIN_SPACING = 1.1  # seconds between sends to one chat
MAX_RETRY_WAIT = 120
CAPTION_LIMIT = 1024


def fit_caption(text: str) -> str:
    if len(text) <= CAPTION_LIMIT:
        return text
    return text[: CAPTION_LIMIT - 1].rstrip() + "…"


class TelegramError(RuntimeError):
    def __init__(self, code: int, description: str):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description


class Telegram:
    def __init__(self, token: str, chat_id: int, thread_id: int = 0):
        self._token = token
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.base = f"https://api.telegram.org/bot{token}/"
        self._session: aiohttp.ClientSession | None = None
        self._queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._last_send = 0.0
        self._file_ids: dict[str, str] = {}

    async def __aenter__(self) -> Telegram:
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        self._worker = asyncio.create_task(self._drain())
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._worker:
            self._worker.cancel()
        if self._session:
            await self._session.close()

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<token>")

    async def _send(self, method: str, *, params: dict | None = None, form: aiohttp.FormData | None = None) -> dict:
        assert self._session, "use `async with Telegram(...)`"
        for attempt in range(5):
            loop = asyncio.get_event_loop()
            gap = MIN_SPACING - (loop.time() - self._last_send)
            if gap > 0:
                await asyncio.sleep(gap)
            try:
                if form is not None:
                    resp_cm = self._session.post(self.base + method, data=self._rebuild(form, params))
                else:
                    resp_cm = self._session.post(self.base + method, json=params)
                async with resp_cm as resp:
                    body = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                log.warning("telegram %s transport error: %s", method, self._redact(str(exc)))
                await asyncio.sleep(2 * (attempt + 1))
                continue
            finally:
                self._last_send = loop.time()
            if body.get("ok"):
                return body["result"]
            code = int(body.get("error_code", 0))
            desc = self._redact(str(body.get("description", "")))
            if code == 429:
                wait = int(body.get("parameters", {}).get("retry_after", 5))
                log.warning("flood wait %ss on %s", wait, method)
                await asyncio.sleep(min(wait, MAX_RETRY_WAIT) + 1)
                continue
            raise TelegramError(code, desc)
        raise TelegramError(0, f"{method}: gave up after retries")

    @staticmethod
    def _rebuild(_form: aiohttp.FormData, factory: dict | None) -> aiohttp.FormData:
        # aiohttp FormData is single-use; the caller passes a factory dict of
        # {name: value | (bytes, filename)} so a retry can build a fresh one.
        form = aiohttp.FormData()
        for name, value in (factory or {}).items():
            if isinstance(value, tuple):
                form.add_field(name, value[0], filename=value[1], content_type="image/png")
            else:
                form.add_field(name, value)
        return form

    def _base_params(self, with_thread: bool) -> dict:
        params: dict[str, Any] = {"chat_id": self.chat_id}
        if with_thread and self.thread_id:
            params["message_thread_id"] = self.thread_id
        return params

    def _cache_file_id(self, key: str | None, result: dict) -> None:
        photos = result.get("photo") or []
        if key and photos:
            self._file_ids[key] = photos[-1]["file_id"]

    async def send_text(self, text: str) -> int:
        params = self._base_params(with_thread=True)
        params.update(parse_mode="HTML", text=text, link_preview_options={"is_disabled": True})
        result = await self._send("sendMessage", params=params)
        return int(result["message_id"])

    async def send_photo(self, photo: Path | str, caption: str) -> int:
        caption = fit_caption(caption)
        key = str(photo) if isinstance(photo, Path) else None
        cached = self._file_ids.get(key) if key else (photo if isinstance(photo, str) else None)
        if cached:
            params = self._base_params(with_thread=True)
            params.update(parse_mode="HTML", caption=caption, photo=cached)
            result = await self._send("sendPhoto", params=params)
        else:
            assert isinstance(photo, Path)
            fields = {str(k): str(v) for k, v in self._base_params(with_thread=True).items()}
            fields.update(parse_mode="HTML", caption=caption, photo=(photo.read_bytes(), photo.name))
            result = await self._send("sendPhoto", form=aiohttp.FormData(), params=fields)
        self._cache_file_id(key, result)
        return int(result["message_id"])

    async def edit_media(self, message_id: int, photo: Path | str, caption: str) -> None:
        caption = fit_caption(caption)
        key = str(photo) if isinstance(photo, Path) else None
        cached = self._file_ids.get(key) if key else (photo if isinstance(photo, str) else None)
        try:
            if cached:
                media = {"type": "photo", "media": cached, "caption": caption, "parse_mode": "HTML"}
                params = self._base_params(with_thread=False)
                params.update(message_id=message_id, media=media)
                result = await self._send("editMessageMedia", params=params)
            else:
                assert isinstance(photo, Path)
                media = {"type": "photo", "media": "attach://banner", "caption": caption, "parse_mode": "HTML"}
                fields = {str(k): str(v) for k, v in self._base_params(with_thread=False).items()}
                fields.update(message_id=str(message_id), media=json.dumps(media),
                              banner=(photo.read_bytes(), photo.name))
                result = await self._send("editMessageMedia", form=aiohttp.FormData(), params=fields)
        except TelegramError as exc:
            if "not modified" in exc.description.lower():
                return
            raise
        self._cache_file_id(key, result)

    def enqueue(self, job: Callable[[], Awaitable[None]]) -> None:
        self._queue.put_nowait(job)

    async def _drain(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await job()
            except TelegramError as exc:
                log.error("telegram job failed: %s", exc)
            except Exception as exc:  # never let one job kill the worker
                log.exception("job crashed: %s", exc)
            finally:
                self._queue.task_done()

    async def me(self) -> dict:
        return await self._send("getMe", params={})
