#!/usr/bin/env python3
"""Fail if the tree carries text that should not reach a public repo.

Run from the repository root:

    python3 tools/check_hygiene.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN = [
    (r"co-authored-by", "co-author trailer"),
    (r"generated with", "generation notice"),
    (r"\bTODO\b|\bFIXME\b|\bXXX\b", "unfinished marker"),
    (r"[—–]", "em or en dash"),
    (r"\bnoqa\b", "linter suppression"),
]

SKIP_DIRS = {".git", "__pycache__", ".ruff_cache", "media", ".venv", "venv", "build", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".toml", ".txt", ".cfg", ".service", ".example", ""}


def tracked_files() -> list[Path]:
    # Tracked plus untracked-not-ignored, so a new file is caught before it is
    # committed, not only after. Deduplicated, order preserved.
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        seen: dict[str, Path] = {}
        for line in out.stdout.splitlines():
            if line:
                seen.setdefault(line, ROOT / line)
        if seen:
            return list(seen.values())
    except (OSError, subprocess.CalledProcessError):
        pass
    return [p for p in ROOT.rglob("*") if not SKIP_DIRS & set(p.parts)]


def main() -> int:
    this_file = Path(__file__).resolve()
    failures = []
    for path in tracked_files():
        if not path.is_file() or path.resolve() == this_file:
            continue
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "Dockerfile":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for pattern, label in FORBIDDEN:
                if re.search(pattern, line, re.IGNORECASE):
                    failures.append(f"{path.relative_to(ROOT)}:{number}: {label}: {line.strip()[:90]}")

    for failure in failures:
        print(failure)
    if failures:
        print(f"\n{len(failures)} problem(s) found.")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
