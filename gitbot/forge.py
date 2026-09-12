"""Read pull request details from the forge's public API. Used to confirm a
merge seen in a push and to fill in the title and author for its message."""
from __future__ import annotations

import logging

from .models import PullRequest, Repo

log = logging.getLogger("gitbot.forge")


def pull_from_json(data: dict, repo: Repo) -> PullRequest:
    return PullRequest(
        repo=repo,
        action="closed",
        number=int(data.get("number", 0) or 0),
        title=data.get("title", ""),
        url=data.get("html_url", ""),
        state=data.get("state", ""),
        merged=bool(data.get("merged", False)),
        base_ref=(data.get("base", {}) or {}).get("ref", ""),
        head_label=(data.get("head", {}) or {}).get("label", ""),
        body=data.get("body", "") or "",
        opener=(data.get("user", {}) or {}).get("login", ""),
    )


class ForgeClient:
    def __init__(self, session, forge_base: str):
        self._session = session
        self._base = forge_base.rstrip("/")

    async def pull(self, repo_full_name: str, number: int) -> dict | None:
        url = f"{self._base}/api/v1/repos/{repo_full_name}/pulls/{number}"
        try:
            async with self._session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
        except Exception as exc:  # public best-effort lookup, never fatal
            log.debug("forge pull %s#%s failed: %s", repo_full_name, number, exc)
            return None
