# nonos-gitbot

Posts commits, pull requests and releases from git.nonos.software into the
Telegram group. It reads a Forgejo organisation webhook, verifies every
delivery, filters the noise, and links to our own forge, never to GitHub.

The full design, event fields and forge-side setup are in the team brief on
the maintainers' side. This README is how to run it.

## What it posts

- Commits pushed to a repository's default branch, showing the commit
  authors rather than the `nonos-sync` account that carries them across.
- Pull requests: opened as a new message, then edited in place as they are
  updated, closed or merged, so each PR is one line that changes state.
- Releases when published.

Each event is posted as a banner image with the message as its caption. A
pull request is one message whose image and caption are swapped together as
it opens, merges or closes.

Everything else (other branches, branch create and delete, draft PRs,
private repos, duplicate deliveries) is dropped.

## Run it

```sh
python3 -m pip install -r requirements.txt
cp .env.example .env          # fill BOT_TOKEN, CHAT_ID, WEBHOOK_SECRET
python3 -m gitbot
```

It listens on `127.0.0.1:3191/forgejo` by default and answers `/healthz`.
The forge admin points the organisation webhook at that address with the
shared secret.

## Security

- Every delivery's HMAC-SHA256 is checked over the raw body before the JSON
  is parsed, in constant time. A bad signature gets a 401 and the payload is
  never logged.
- The bot token and webhook secret load from files or a systemd credential,
  never from the process environment, and are redacted from logs.
- It listens on loopback only and talks outbound to `api.telegram.org` and
  the forge.

## Deploy

`deploy/gitbot.service` runs it as its own user with `ProtectSystem=strict`,
no capabilities, private tmp, and secrets via `LoadCredential`. Put the two
secret files under `/etc/nonos-gitbot/`, install the unit, and enable it.

## Tests

```sh
python3 -m unittest discover -s tests -t .
```

37 tests, no network: HMAC verification, event parsing, the noise filters,
message rendering, author recovery, dedup and the PR edit-in-place flow.

## Layout

```
gitbot/config.py     environment, validated at start
gitbot/webhook.py    receiver: verify, dedup, fast 202, dispatch
gitbot/events.py     parse Forgejo payloads into model objects
gitbot/models.py     the data shapes and their derived properties
gitbot/filters.py    what to post, edit or drop
gitbot/authors.py    recover the real author of a synced PR
gitbot/render.py     message shapes (HTML)
gitbot/banners.py    which banner image goes with which event
gitbot/telegram.py   Bot API client with a serialising, rate-limited worker
gitbot/handler.py    events to Telegram jobs
gitbot/state.py      dedup ring and PR message map, atomic 0600
gitbot/app.py        wiring and shutdown
```
