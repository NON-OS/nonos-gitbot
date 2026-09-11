"""Turn a verified webhook into Telegram work: decide, render, enqueue.

Commit pushes are held briefly and coalesced per branch by the batcher, so a
burst becomes one message. A new repository is announced once. Pull requests
and releases post immediately, and a pull request stays one message whose
banner and caption change together as it opens, merges or closes. An event
whose banner is not present yet falls back to a plain text message rather
than failing.
"""
from __future__ import annotations

import logging

from . import banners, events, filters, models, render
from .authors import SyncSummary
from .batcher import CommitBatcher, merge
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
        self.batcher = CommitBatcher(cfg.batch_seconds, self._flush_commits)

    def dispatch(self, event_type: str, payload: dict) -> None:
        if event_type == "push":
            self._push(events.parse_push(payload))
        elif event_type == "pull_request":
            self._pull_request(events.parse_pull_request(payload))
        elif event_type == "release":
            self._release(events.parse_release(payload))
        else:
            log.debug("dropping event type %s", event_type)

    def _post_banner(self, banner_name: str, text: str) -> None:
        """Enqueue a photo post, or a plain message if the banner is missing."""
        banner = banners.path(self.cfg.media_dir, banner_name)
        if banner.is_file():
            self.tg.enqueue(lambda: self.tg.send_photo(banner, text))
        else:
            log.info("banner %s not present, posting as text", banner_name)
            self.tg.enqueue(lambda: self.tg.send_text(text))

    def _push(self, push: models.Push) -> None:
        decision, reason = filters.decide_push(push)
        log.info("push %s %s: %s (%s)", push.repo.full_name, push.branch, decision, reason)
        if decision == filters.SKIP:
            return
        if decision == filters.REPO:
            self._post_banner(banners.REPO_NEW, render.render_repo_new(push))
            return
        if push.is_tag:
            text = render.render_push(push, self.cfg.max_commits, self.cfg.summary_chars)
            self.tg.enqueue(lambda: self.tg.send_text(text))
            return
        self.batcher.add(push)

    def _flush_commits(self, pushes: list[models.Push]) -> None:
        merged = merge(pushes)
        text = render.render_push(merged, self.cfg.max_commits, self.cfg.summary_chars)
        self._post_banner(banners.COMMITS, text)

    def _pull_request(self, pr: models.PullRequest) -> None:
        decision, reason = filters.decide_pull_request(pr, self.cfg.skip_drafts)
        log.info("pull_request %s #%s %s: %s (%s)", pr.repo.full_name, pr.number, pr.action, decision, reason)
        if decision == filters.SKIP:
            return

        async def job() -> None:
            author = await self.summary.author_for(pr)
            text = render.render_pull_request(pr, author)
            banner = banners.path(self.cfg.media_dir, banners.for_pull_request(pr))
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
        self._post_banner(banners.RELEASE, render.render_release(release))
