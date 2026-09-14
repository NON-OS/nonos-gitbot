# Changelog

## Unreleased

- Read-only group commands answered from the forge API: /prs, /latest, /repo,
  /status, /help. Rate limited, answered only in the configured chat or in
  private. Needs group privacy off so the bot can see the commands.

- Poll the forge for pull request changes. The forge does not fire
  pull_request webhooks for its sync-driven activity, so the bot only ever saw
  main pushes. It now reads the forge PR API on an interval (PR_POLL_SECONDS,
  default 90) and announces a pull request when it opens, gets new commits,
  merges or closes, editing the one message per PR. The first run learns the
  current state without posting so it does not flood the group.

- Read a merge commit as a merged pull request. A merge done on GitHub reaches
  the forge as a push, not a pull_request event, so the merge is recognised
  from the commit subject, confirmed against the forge API, and announced as a
  merged PR that edits the existing message, instead of a generic "new commits
  on main".
- Announce a new repository once, when its first push creates the default
  branch with commits, instead of arriving silently.
- Batch commit pushes per repository and branch for a short window
  (`BATCH_SECONDS`, default 60) so a burst becomes one message. Pull requests
  and releases still post immediately.
- Richer releases: list the files with their sizes and surface a checksums
  asset, within the caption limit.
- Alert a private admin chat (`ADMIN_CHAT_ID`) when Telegram sends or webhook
  signatures keep failing, at most once an hour per fault.
- Pin `aiohttp` to the deployed version. A fully hash-pinned lock is a
  follow-up; generate it with pip-tools on the server.
- Events whose banner is not present yet fall back to a plain text message
  rather than failing.

## 1.0.0

- First release. Posts commits, pull requests and releases from
  git.nonos.software to Telegram, verifying every webhook delivery over the
  raw body, deduplicating by delivery id, and editing a pull request in place
  as it opens, merges or closes. Each event carries a banner.
