"""Recognise pull request merges inside a push to the default branch.

Merges done on GitHub reach the forge as a push carrying the merge commit,
not as a pull_request webhook, so the merge has to be read out of the commit
messages. A merge commit reads "Merge pull request #12 ...", a squash or
rebase merge ends its subject with "(#12)".
"""
from __future__ import annotations

import re

from .models import Commit

_MERGE_COMMIT = re.compile(r"Merge pull request #(\d+)")
_SQUASH_SUFFIX = re.compile(r"\(#(\d+)\)")


def pr_numbers(commits: list[Commit]) -> list[int]:
    numbers: list[int] = []
    for commit in commits:
        subject = commit.message.splitlines()[0] if commit.message else ""
        for pattern in (_MERGE_COMMIT, _SQUASH_SUFFIX):
            for match in pattern.finditer(subject):
                n = int(match.group(1))
                if n not in numbers:
                    numbers.append(n)
    return numbers
