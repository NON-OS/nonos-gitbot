"""Hold commit pushes for a short window per repository and branch, then send
one message. Several pushes to the same branch in quick succession become a
single post instead of a burst. Pull requests and releases do not pass
through here; they post immediately."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from .models import Push

log = logging.getLogger("gitbot.batch")

# Flush renders and enqueues, both synchronous, so the timer path and the
# window-off path share one code path and tests need no clock.
FlushFn = Callable[[list[Push]], None]


def merge(pushes: list[Push]) -> Push:
    """Combine pushes to the same branch into one, oldest first, spanning the
    whole range from the first push's parent to the last push's tip."""
    first, last = pushes[0], pushes[-1]
    repo = first.repo
    commits = [c for p in pushes for c in p.commits]
    compare = last.compare_url
    if first.before and last.after and repo.html_url:
        compare = f"{repo.html_url}/compare/{first.before}...{last.after}"
    return Push(
        repo=repo,
        ref=first.ref,
        before=first.before,
        after=last.after,
        compare_url=compare,
        total_commits=sum(p.total_commits for p in pushes),
        commits=commits,
        pusher=last.pusher,
    )


class CommitBatcher:
    def __init__(self, window_seconds: float, flush: FlushFn):
        self.window = window_seconds
        self._flush = flush
        self._buffers: dict[tuple[str, str], list[Push]] = {}
        self._tasks: dict[tuple[str, str], asyncio.Task] = {}

    def add(self, push: Push) -> None:
        if self.window <= 0:
            self._flush([push])
            return
        key = (push.repo.full_name, push.branch)
        self._buffers.setdefault(key, []).append(push)
        if key not in self._tasks or self._tasks[key].done():
            self._tasks[key] = asyncio.ensure_future(self._run(key))

    async def _run(self, key: tuple[str, str]) -> None:
        try:
            await asyncio.sleep(self.window)
        except asyncio.CancelledError:
            pass
        pushes = self._buffers.pop(key, [])
        self._tasks.pop(key, None)
        if pushes:
            self._flush(pushes)

    def flush_all(self) -> None:
        """Send anything still held, for a clean shutdown."""
        for task in list(self._tasks.values()):
            task.cancel()
        for key in list(self._buffers):
            pushes = self._buffers.pop(key, [])
            if pushes:
                self._flush(pushes)
        self._tasks.clear()
