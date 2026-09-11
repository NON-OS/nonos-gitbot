"""Noise rules. The kernel alone has hundreds of branches, so without these
the group becomes a firehose. Each function returns a decision plus a short
reason for the debug log."""
from __future__ import annotations

from .models import PullRequest, Push, Release

POST = "post"
EDIT = "edit"
SKIP = "skip"
REPO = "repo"

# A pull request is one line in the group that changes state: it is posted
# once when opened, then every later action edits that same message.
PR_POST_ACTIONS = {"opened"}
PR_EDIT_ACTIONS = {"reopened", "closed", "synchronized", "edited"}


def decide_push(push: Push) -> tuple[str, str]:
    if push.repo.private:
        return SKIP, "private repository"
    if push.is_tag:
        return (POST, "tag created") if not push.is_deleted_branch else (SKIP, "tag deleted")
    if (push.is_new_branch and not push.is_deleted_branch
            and push.branch == push.repo.default_branch and (push.commits or push.total_commits)):
        return REPO, "new repository"
    if push.is_new_branch or push.is_deleted_branch:
        return SKIP, "branch create or delete"
    if push.branch != push.repo.default_branch:
        return SKIP, f"non-default branch {push.branch}"
    if not push.commits and push.total_commits == 0:
        return SKIP, "no commits"
    return POST, "default-branch push"


def decide_pull_request(pr: PullRequest, skip_drafts: bool) -> tuple[str, str]:
    if pr.repo.private:
        return SKIP, "private repository"
    if pr.action in PR_POST_ACTIONS:
        if pr.action == "opened" and skip_drafts and pr.is_draft:
            return SKIP, "draft pull request"
        return POST, f"pull request {pr.action}"
    if pr.action in PR_EDIT_ACTIONS:
        return EDIT, f"pull request {pr.action}"
    return SKIP, f"ignored action {pr.action or 'none'}"


def decide_release(release: Release) -> tuple[str, str]:
    if release.repo.private:
        return SKIP, "private repository"
    if release.action != "published":
        return SKIP, f"ignored action {release.action or 'none'}"
    return POST, "release published"
