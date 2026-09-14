# Operations

What the bot posts, what it drops, and how the messages read. The rules live
in `filters.py` and the shapes in `render.py`.

## Webhook events to enable

On the Forgejo organisation webhook, content type JSON, method POST, enable:

- Push
- Branch or tag creation
- Pull request
- Release

Leave the rest off. The bot also drops any event type it did not ask for, so
an over-broad webhook is harmless, just wasteful.

## What gets posted

**Commits.** Only pushes to a repository's default branch. The message shows
how many commits and who wrote them, taken from the commit authors, not the
`nonos-sync` account that carries them across. At most five commit subjects,
then "and N more" linking to the whole diff. Subjects are the first line
only, trimmed to about ninety characters.

**Pull requests.** Posted once when opened. Every later event, a new push to
the branch, a close, a merge, edits that same message so a pull request is
one line that changes its own state. A title starting with WIP is treated as
a draft and skipped until it is renamed, unless `SKIP_DRAFTS` is off.

**Releases.** Posted when published, with the tag, the name and the asset
count.

## What gets dropped

- Pushes to any branch other than the default. That work arrives as a pull
  request anyway.
- New and deleted branches. Tags still produce a line.
- Draft pull requests, until marked ready.
- Anything in a private repository. All of ours are public today; the check
  is there for the day one is not.
- Duplicate deliveries. Forgejo retries, and admins can redeliver by hand.

## Pull requests

The forge is fed from GitHub by a sync account and does not fire pull_request
webhooks for that activity, so the bot does not learn about pull requests from
the webhook stream. Instead it polls the forge PR API every PR_POLL_SECONDS and
posts when a pull request opens, gets new commits, merges or closes, keeping one
message per pull request that is edited in place. The first run after a fresh
state learns the current open pull requests without posting them.

## Banners

Every posted event carries a banner rendered from the site's design, with
the message as the caption: commits, pull request opened, merged and closed,
and release. A pull request keeps one message; its banner and caption are
swapped together with editMessageMedia as it opens, merges or closes. Tags
have no banner and go as a plain message. The images live in the media
directory and come from nonos-next/tools/forge/banners/, so a wording change
is a rerun of that tool, not a code change. A photo caption is limited to
1024 characters, so a long commit list is trimmed to fit.

## Message shapes

A push:

```
NON-OS/nonos-micro-kernel · main
3 commits by eKisNonos

· Directory records as one layout
· Same-length replacement in the store
· Reply inbox names stored inline
View the diff
```

A pull request, which becomes "Pull request merged" in place when it lands:

```
Pull request opened · nonos-micro-kernel #12
A key only this machine can derive
by eKisNonos · main (GitHub #485)
https://git.nonos.software/NON-OS/nonos-micro-kernel/pulls/12
```

## Tuning

- `MAX_COMMITS` and `SUMMARY_CHARS` control how much of a big push is shown.
- `SKIP_DRAFTS=0` posts WIP pull requests immediately.
- To move the feed to a different group, change `CHAT_ID`. To post into one
  topic of a group that uses topics, set `MESSAGE_THREAD_ID`.

## Rate limits

Telegram allows roughly one message per second to a chat and about twenty a
minute in a group. The bot serialises all sends through one worker with a
small gap between them, and on a 429 waits the delay Telegram returns. A
push of forty commits is one message, not forty, so the limit is rarely near.
