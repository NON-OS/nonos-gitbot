# Changelog

## Unreleased

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
