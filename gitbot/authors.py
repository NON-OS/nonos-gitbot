"""Recover the real author of a synced pull request.

git.nonos.software is fed from GitHub by an account called `nonos-sync`, so
the pusher and the PR opener here are almost always that account. The real
author is named in the last line of the PR description, and as a fallback
can be looked up by GitHub number in the forge's public sync summary.
"""
from __future__ import annotations

import logging
import re
import time

from .models import PullRequest

log = logging.getLogger("gitbot.authors")

SYNC_ACCOUNT = "nonos-sync"
# "Opened on GitHub by eKisNonos as pull request 485."
_BODY_AUTHOR = re.compile(r"on GitHub by\s+([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})?)\b", re.IGNORECASE)


def author_from_body(body: str) -> str:
    match = _BODY_AUTHOR.search(body or "")
    return match.group(1) if match else ""


class SyncSummary:
    """Caches the forge's public sync.json and maps a repo plus GitHub PR
    number to the real author. No token needed; the file is public."""

    def __init__(self, session, forge_base: str, ttl: float = 300.0):
        self._session = session
        self._url = f"{forge_base}/assets/nn/sync.json"
        self._ttl = ttl
        self._at = 0.0
        self._by: dict[tuple[str, str], str] = {}

    async def _refresh(self) -> None:
        if time.monotonic() - self._at < self._ttl:
            return
        try:
            async with self._session.get(self._url, timeout=10) as resp:
                data = await resp.json(content_type=None)
            table: dict[tuple[str, str], str] = {}
            for item in ((data.get("pulls", {}) or {}).get("items", []) or []):
                repo = str(item.get("repo", ""))
                number = str(item.get("number", ""))
                by = str(item.get("by", ""))
                if repo and number and by:
                    table[(repo, number)] = by
            self._by = table
            self._at = time.monotonic()
        except Exception as exc:  # public best-effort lookup, never fatal
            log.debug("sync.json fetch failed: %s", exc)

    async def author_for(self, pr: PullRequest) -> str:
        from_body = author_from_body(pr.body)
        if from_body:
            return from_body
        if pr.opener and pr.opener != SYNC_ACCOUNT:
            return pr.opener
        gh = pr.gh_number
        if gh:
            await self._refresh()
            hit = self._by.get((pr.repo.full_name, gh)) or self._by.get((pr.repo.full_name.split("/")[-1], gh))
            if hit:
                return hit
        return pr.opener or SYNC_ACCOUNT
