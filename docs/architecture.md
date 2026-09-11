# Architecture

The bot turns a Forgejo webhook into Telegram messages. This document
follows one delivery from the forge to the group and explains why each part
is built the way it is.

## The path of a delivery

```
Forgejo POST
      │
      ▼
  verify HMAC over the raw body   reject with 401 if it fails
      │
      ▼
  drop duplicates by delivery id  answer 202, do nothing
      │
      ▼
  answer 202 fast                 Forgejo gives up on slow receivers
      │
      ▼
  parse and filter                default branch only, PRs, releases
      │
      ▼
  render and enqueue              one job on the Telegram worker
      │
      ▼
  Telegram worker                 spaced sends, 429 honoured
```

The receiver never does slow work before answering. It verifies, dedupes,
answers 202, and hands the event to the handler, which drops a job on a
queue. A single worker drains that queue so a large push becomes a steady
trickle rather than a burst that trips Telegram's rate limit.

## Why it reads Forgejo, not GitHub

The point of the bot is to send people to our own forge. git.nonos.software
is kept in step with GitHub by an account called `nonos-sync`, so the code
lands on the forge and the webhook fires there. The bot links only to
git.nonos.software and never to GitHub.

That sync account is also why the bot shows commit authors rather than the
pusher. On almost every push the pusher is `nonos-sync`; the people who
wrote the code are in `commits[].author`. For a pull request carried across,
the real author is named in the last line of the description, and as a
fallback is looked up by GitHub number in the forge's public sync summary.
That logic lives in `authors.py`.

## Verifying a delivery

Forgejo signs each delivery with an HMAC-SHA256 of the raw request body,
keyed by the shared secret. The bot recomputes it over the exact bytes,
before any JSON parsing, and compares in constant time. This matters:
parsing and re-serialising the body would reorder keys and change the
digest, so the check has to run on what arrived. A failed check gets a 401
with no body, and only the delivery id is logged, never the payload.

## A pull request is one line that changes state

The naive design posts a message for every pull request event, which floods
the group with near-duplicates as a PR is opened, pushed to, and merged.
Instead the bot posts once when a PR opens, remembers the Telegram message
id keyed by repository and number, and edits that same message on every
later event. Open becomes merged in place, image and caption swapped together with editMessageMedia. The map lives in `state.py` and
is bounded so it cannot grow without limit.

If the bot restarts and later sees an update for a PR it never saw open, it
has no stored message, so it posts a fresh one rather than dropping the
event.

## Durability

Two things persist to `state.json`: the ring of recent delivery ids for
dedup, and the PR-to-message map. The file is written atomically at mode
600. A corrupt or unreadable file is logged and replaced by an empty state
rather than crashing the process, so an old file never blocks a restart.

Forgejo retries failed deliveries and an admin can redeliver by hand, so
dedup is what keeps a retried delivery from posting twice.

## Failure behaviour

- A render or dispatch bug never fails the delivery; it is logged and the
  bot still answers 202, because a 500 would make Forgejo retry a delivery
  that will fail again.
- A Telegram send that fails is logged and the worker moves on, so one bad
  message cannot wedge the queue.
- On a 429 the worker waits the `retry_after` Telegram returns, capped, then
  continues.
- The bot token and webhook secret are redacted from every log line.

## Module map

| Module | Responsibility |
| --- | --- |
| `config` | environment parsing and validation, secret loading |
| `webhook` | receiver: verify, dedup, fast 202, dispatch |
| `events` | parse Forgejo payloads into model objects |
| `models` | the data shapes and their derived properties |
| `filters` | decide post, edit or drop |
| `authors` | recover the real author of a synced pull request |
| `render` | message HTML |
| `banners` | which banner image goes with which event |
| `telegram` | Bot API client and the serialising, rate-limited worker |
| `handler` | events to Telegram jobs |
| `state` | dedup ring and PR message map |
| `app` | wiring, preflight, shutdown |

Dependencies point one way. `app` knows everything; `handler` knows the
renderer, filters and Telegram; the leaves know nothing about the rest. No
module imports `app`.
