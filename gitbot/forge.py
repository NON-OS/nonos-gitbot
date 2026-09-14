"""Read pull requests from the forge's public API.

The forge is fed from GitHub by a sync account and does not fire pull_request
webhooks for that activity, so the bot polls this API to see pull requests
open, update, merge and close, and uses it to confirm a merge seen in a push.
"""

from __future__ import annotations

import logging
import time

from .models import PullRequest, Repo

log = logging.getLogger("gitbot.forge")


def pull_from_json(data: dict, repo: Repo) -> PullRequest:
    state = data.get("state", "")
    return PullRequest(
        repo=repo,
        action="closed" if state == "closed" else "opened",
        number=int(data.get("number", 0) or 0),
        title=data.get("title", ""),
        url=data.get("html_url", ""),
        state=state,
        merged=bool(data.get("merged", False)),
        base_ref=(data.get("base", {}) or {}).get("ref", ""),
        head_label=(data.get("head", {}) or {}).get("label", ""),
        body=data.get("body", "") or "",
        opener=(data.get("user", {}) or {}).get("login", ""),
        head_sha=(data.get("head", {}) or {}).get("sha", ""),
        changed_files=int(data.get("changed_files", 0) or 0),
        draft=bool(data.get("draft", False)),
    )


class ForgeClient:
    def __init__(self, session, forge_base: str):
        self._session = session
        self._base = forge_base.rstrip("/")
        self._repos: list[str] = []
        self._repos_at = 0.0

    async def _get(self, path: str):
        try:
            async with self._session.get(f"{self._base}/api/v1{path}", timeout=15) as resp:
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
        except Exception as exc:  # public best-effort lookup, never fatal
            log.debug("forge GET %s failed: %s", path, exc)
            return None

    async def pull(self, repo_full_name: str, number: int) -> dict | None:
        return await self._get(f"/repos/{repo_full_name}/pulls/{number}")

    async def list_pulls(self, repo_full_name: str, limit: int = 30) -> list[dict]:
        data = await self._get(f"/repos/{repo_full_name}/pulls?state=all&sort=recentupdate&limit={limit}")
        return data if isinstance(data, list) else []

    async def org_repos(self, org: str, ttl: float = 3600.0) -> list[str]:
        if self._repos and time.monotonic() - self._repos_at < ttl:
            return self._repos
        names: list[str] = []
        for page in range(1, 11):
            data = await self._get(f"/orgs/{org}/repos?limit=50&page={page}")
            if not isinstance(data, list) or not data:
                break
            names.extend(r["full_name"] for r in data if not r.get("archived"))
            if len(data) < 50:
                break
        if names:
            self._repos = names
            self._repos_at = time.monotonic()
        return self._repos
