"""Poll the forge for pull request changes.

The forge does not fire pull_request webhooks for its sync-driven activity, so
the webhook stream only ever carries pushes. This poller reads the forge's PR
API on an interval, notices when a pull request opens, gets new commits, merges
or closes, and announces it, editing the one message per pull request in place.
The first run learns the current state without posting, so it does not flood the
group with the existing open pull requests.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from .config import Config
from .forge import ForgeClient, pull_from_json
from .models import PullRequest, Repo
from .state import State

log = logging.getLogger("gitbot.poll")


class PRPoller:
    def __init__(
        self, cfg: Config, forge: ForgeClient, state: State, announce: Callable[[PullRequest], Awaitable[None]]
    ):
        self.cfg = cfg
        self.forge = forge
        self.state = state
        self.announce = announce
        self._seeded = bool(state.pr_state)

    async def run(self) -> None:
        if self.cfg.pr_poll_seconds <= 0:
            log.info("pull request polling disabled")
            return
        log.info(
            "polling pull requests every %ds%s",
            self.cfg.pr_poll_seconds,
            "" if self._seeded else " (first run learns current state silently)",
        )
        while True:
            try:
                await self._cycle()
            except Exception as exc:  # keep polling
                log.error("pr poll cycle failed: %s", exc)
            await asyncio.sleep(self.cfg.pr_poll_seconds)

    async def _cycle(self) -> None:
        for full in await self.forge.org_repos(self.cfg.org):
            await self._poll_repo(full)
        self._seeded = True

    async def _poll_repo(self, full: str) -> None:
        pulls = await self.forge.list_pulls(full)
        if not pulls:
            return
        repo = Repo(full, f"{self.cfg.forge_base}/{full}", "main", False)
        changed = False
        for data in pulls:
            pr = pull_from_json(data, repo)
            if not pr.number:
                continue
            key = self.state.pr_key(full, pr.number)
            signature = f"{pr.state}:{pr.merged}:{pr.head_sha}"
            if self.state.pr_signature(key) == signature:
                continue
            first_seen = self.state.pr_signature(key) is None
            self.state.set_pr_signature(key, signature)
            changed = True
            if not self._seeded:
                continue
            if first_seen and pr.state == "open" and pr.is_draft and self.cfg.skip_drafts:
                continue
            log.info("pull request %s #%s changed: %s", full, pr.number, signature)
            await self.announce(pr)
        if changed:
            self.state.save(self.cfg.state_file)
