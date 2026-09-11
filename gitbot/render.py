"""Message shapes. Plain and scannable, the same voice as the site. Every
dynamic value is HTML-escaped; only the fixed markup is raw."""
from __future__ import annotations

import html

from .models import Commit, PullRequest, Push, Release


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def first_line(message: str, limit: int) -> str:
    line = (message or "").splitlines()[0] if message else ""
    line = line.strip()
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


def _author_label(commits: list[Commit]) -> str:
    names = []
    for c in commits:
        name = c.author_login or c.author_name
        if name and name not in names:
            names.append(name)
    if not names:
        return "unknown"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{names[0]} and {len(names) - 1} others"


def render_push(push: Push, max_commits: int, summary_chars: int) -> str:
    if push.is_tag:
        head = f"<b>{_esc(push.repo.full_name)}</b> · tag {_esc(push.tag_name)}"
        link = f"{push.repo.html_url}/releases/tag/{html.escape(push.tag_name, quote=True)}"
        return f"{head}\nTag created\n<a href=\"{link}\">View the tag</a>"

    n = push.total_commits or len(push.commits)
    plural = "commit" if n == 1 else "commits"
    head = f"<b>{_esc(push.repo.full_name)}</b> · {_esc(push.branch)}\n{n} {plural} by {_esc(_author_label(push.commits))}"
    lines = [head, ""]
    for c in push.commits[:max_commits]:
        lines.append(f"· {_esc(first_line(c.message, summary_chars))}")
    hidden = n - min(len(push.commits), max_commits)
    if hidden > 0:
        lines.append(f"· and {hidden} more")
    if push.compare_url:
        lines.append(f"<a href=\"{push.compare_url}\">View the diff</a>")
    return "\n".join(lines)


def _pr_headline(pr: PullRequest) -> str:
    if pr.action == "closed" and pr.merged:
        verb = "merged"
    elif pr.action == "closed":
        verb = "closed"
    elif pr.action == "reopened":
        verb = "reopened"
    else:
        verb = "opened"
    return f"Pull request {verb}"


def render_pull_request(pr: PullRequest, author: str) -> str:
    head = f"<b>{_esc(_pr_headline(pr))}</b> · {_esc(pr.repo.full_name)} #{pr.number}"
    title = _esc(pr.title)
    meta = f"by {_esc(author)}"
    if pr.base_ref:
        meta += f" · {_esc(pr.base_ref)}"
    if pr.gh_number:
        meta += f" (GitHub #{_esc(pr.gh_number)})"
    return f"{head}\n{title}\n{meta}\n<a href=\"{pr.url}\">{_esc(pr.url)}</a>"


def render_release(release: Release) -> str:
    name = release.name or release.tag_name
    head = f"<b>Release published</b> · {_esc(release.repo.full_name)}"
    lines = [head, _esc(name)]
    if release.assets:
        lines.append(f"{len(release.assets)} asset" + ("" if len(release.assets) == 1 else "s"))
    lines.append(f"<a href=\"{release.url}\">{_esc(release.url)}</a>")
    return "\n".join(lines)
