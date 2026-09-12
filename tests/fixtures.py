"""Realistic Forgejo 16.x webhook payloads, trimmed to the fields the bot reads."""

REPO = {
    "full_name": "NON-OS/nonos-micro-kernel",
    "html_url": "https://git.nonos.software/NON-OS/nonos-micro-kernel",
    "default_branch": "main",
    "private": False,
}

ZERO = "0" * 40


def push(
    ref="refs/heads/main", commits=None, pusher="nonos-sync", total=None, before="a" * 40, after="b" * 40, repo=None
):
    commits = (
        commits
        if commits is not None
        else [
            {
                "id": "c1" + "0" * 38,
                "message": "Directory records as one layout\n\nbody",
                "url": "https://git.nonos.software/x/1",
                "author": {"name": "eK", "username": "eKisNonos"},
            },
        ]
    )
    return {
        "ref": ref,
        "before": before,
        "after": after,
        "compare_url": "https://git.nonos.software/NON-OS/nonos-micro-kernel/compare/aaa...bbb",
        "total_commits": total if total is not None else len(commits),
        "commits": commits,
        "pusher": {"login": pusher},
        "repository": repo or REPO,
    }


def commit(msg, login="eKisNonos", name="eK"):
    return {
        "id": "0" * 40,
        "message": msg,
        "url": "https://git.nonos.software/x",
        "author": {"name": name, "username": login},
    }


def pull_request(
    action="opened",
    number=12,
    title="A vault the wallet keeps",
    merged=False,
    state="open",
    head_label="eKisNonos/nonos-micro-kernel:gh-485",
    body="Some description.\nOpened on GitHub by eKisNonos as pull request 485.",
    opener="nonos-sync",
    base_ref="main",
    repo=None,
):
    return {
        "action": action,
        "number": number,
        "pull_request": {
            "number": number,
            "title": title,
            "html_url": f"https://git.nonos.software/NON-OS/nonos-micro-kernel/pulls/{number}",
            "state": state,
            "merged": merged,
            "merged_at": "2026-09-11T10:00:00Z" if merged else None,
            "base": {"ref": base_ref},
            "head": {"label": head_label},
            "body": body,
            "user": {"login": opener},
        },
        "repository": repo or REPO,
    }


def release(action="published", tag="v0.9.2", name="NONOS 0.9.2", repo=None):
    return {
        "action": action,
        "release": {
            "tag_name": tag,
            "name": name,
            "html_url": f"https://git.nonos.software/NON-OS/nonos-micro-kernel/releases/tag/{tag}",
            "assets": [{"name": "nonos.iso", "size": 36700160}],
        },
        "repository": repo or REPO,
    }
