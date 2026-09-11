"""Turn a verified webhook into Telegram work: decide, render, enqueue.

Each event is posted as a banner with the message as its caption. A pull
request is one message: it opens with the opened banner, then its image and
caption are swapped together as it merges or closes, so the group sees one
line that changes state rather than a stream of near-duplicates. Dedup
already happened in the webhook layer.
"""
from __future__ import annotations

import logging

from . import banners, events, filters, models, render
from .authors import SyncSummary
from .config import Config
from .state import State
from .telegram import Telegram

log = logging.getLogger("gitbot.handler")


class Handler:
    def __init__(self, cfg: Config, tg: Telegram, state: State, summary: SyncSummary):
        self.cfg = cfg
        self.tg = tg
        self.state = state
        self.summary = summary

    def dispatch(self, event_type: str, payload: dict) -> None:
        if event_type == "push":
            self._push(events.parse_push(payload))
        elif event_type == "pull_request":
            self._pull_request(events.parse_pull_request(payload))
        elif event_type == "release":
            self._release(events.parse_release(payload))
        else:
            log.debug("dropping event type %s", event_type)

    def _banner(self, name: str):
        return banners.path(self.cfg.media_dir, name)

    def _push(self, push: models.Push) -> None:
        decision, reason = filters.decide_push(push)
        log.info("push %s %s: %s (%s)", push.repo.full_name, push.branch, decision, reason)
        if decision != filters.POST:
            return
        text = render.render_push(push, self.cfg.max_commits, self.cfg.summary_chars)

        # A tag has no banner of its own, so it goes as a plain message.
        if push.is_tag:
            async def tag_job() -> None:
                await self.tg.send_text(text)
            self.tg.enqueue(tag_job)
            return

        banner = self._banner(banners.COMMITS)

        async def job() -> None:
            await self.tg.send_photo(banner, text)

        self.tg.enqueue(job)

    def _pull_request(self, pr: models.PullRequest) -> None:
        decision, reason = filters.decide_pull_request(pr, self.cfg.skip_drafts)
        log.info("pull_request %s #%s %s: %s (%s)", pr.repo.full_name, pr.number, pr.action, decision, reason)
        if decision == filters.SKIP:
            return

        async def job() -> None:
            author = await self.summary.author_for(pr)
            text = render.render_pull_request(pr, author)
            banner = self._banner(banners.for_pull_request(pr))
            existing = self.state.pr_message(pr.repo.full_name, pr.number)
            if existing:
                await self.tg.edit_media(existing, banner, text)
                return
            if decision == filters.EDIT:
                log.info("no stored message for %s #%s; posting fresh", pr.repo.full_name, pr.number)
            message_id = await self.tg.send_photo(banner, text)
            self.state.remember_pr(pr.repo.full_name, pr.number, message_id)
            self.state.save(self.cfg.state_file)

        self.tg.enqueue(job)

    def _release(self, release: models.Release) -> None:
        decision, reason = filters.decide_release(release)
        log.info("release %s %s: %s (%s)", release.repo.full_name, release.tag_name, decision, reason)
        if decision != filters.POST:
            return
        text = render.render_release(release)
        banner = self._banner(banners.RELEASE)

        async def job() -> None:
            await self.tg.send_photo(banner, text)

        self.tg.enqueue(job)
