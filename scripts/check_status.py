#!/usr/bin/env python3
"""Fail when STATUS.md has stopped telling the truth.

STATUS.md is the file that rots fastest, and a rotted one is worse than a
missing one because it is trusted. This is the check that can return "no".

    python scripts/check_status.py [root] [--strict] [--path DIR ...]

Default mode (CI, test suites): structure, placeholders, and committed
staleness - code committed after the STATUS.md date is a failure.

--strict (pre-commit hooks): also requires STATUS.md to be part of the
current diff whenever a code path is dirty. Updating STATUS.md is part of
the change, not follow-up.

Stdlib only. Exit 0 clean, 1 on any finding.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
DATE_RE = re.compile(r"^Last updated:\s*(\d{4})-(\d{2})-(\d{2})\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")

# Normalized heading text -> the question that section answers. All required:
# a STATUS.md that cannot say "broken" is decoration.
REQUIRED_SECTIONS = {
    "works": "what is true",
    "broken / stale": "what is false",
    "next": "what is unfinished",
}
SECTION_ALIASES = {"broken/stale": "broken / stale"}

DEFAULT_CODE_PATHS = ["src", "tests", "scripts", "ops"]


def normalize(heading: str) -> str:
    key = " ".join(heading.lower().split())
    return SECTION_ALIASES.get(key, key)


def sections(body: str) -> dict[str, list[str]]:
    """Map normalized heading -> its body lines, comments and blanks dropped."""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            current = normalize(m.group(1))
            found.setdefault(current, [])
            continue
        if current is None:
            continue
        text = line.strip()
        if not text or text.startswith("<!--"):
            continue
        found[current].append(text)
    return found


def is_stale(status_date: _dt.date, last_code_change: _dt.date | None) -> bool:
    """Pure decision, kept free of git so it can be tested directly."""
    if last_code_change is None:
        return False
    return last_code_change > status_date


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, check=False,
        )
    except (OSError, ValueError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def last_code_commit_date(root: Path, paths: list[str]) -> _dt.date | None:
    """Date of the newest commit touching a code path, or None if unknowable."""
    if _git(root, "rev-parse", "--git-dir") is None:
        return None
    stamp = _git(root, "log", "-1", "--format=%cs", "--", *paths)
    if not stamp:
        return None
    try:
        return _dt.date.fromisoformat(stamp)
    except ValueError:
        return None


def dirty_paths(root: Path) -> list[str] | None:
    """Repo-relative paths with uncommitted changes, or None if unknowable."""
    if _git(root, "rev-parse", "--git-dir") is None:
        return None
    porcelain = _git(root, "status", "--porcelain")
    if porcelain is None:
        return None
    out = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:  # rename: the destination is what changed
            path = path.split(" -> ", 1)[1]
        out.append(path.strip().strip('"'))
    return out


def check(root: Path, code_paths: list[str], strict: bool = False) -> list[str]:
    """Return one line per finding. Empty list means the file is honest."""
    findings: list[str] = []
    status = root / "STATUS.md"
    if not status.is_file():
        return ["STATUS.md is missing"]

    body = status.read_text(encoding="utf-8")

    for m in PLACEHOLDER_RE.finditer(body):
        findings.append(f"STATUS.md still holds an unresolved placeholder: {m.group(1)}")

    found = sections(body)
    for name, question in REQUIRED_SECTIONS.items():
        if name not in found:
            findings.append(f"STATUS.md has no '{name}' section ({question})")
        elif not found[name]:
            findings.append(
                f"STATUS.md section '{name}' is empty - say so explicitly ({question})"
            )

    date_match = DATE_RE.search(body)
    if not date_match:
        findings.append("STATUS.md has no parseable 'Last updated: YYYY-MM-DD' line")
        return findings

    try:
        status_date = _dt.date(*(int(g) for g in date_match.groups()))
    except ValueError:
        findings.append(f"STATUS.md 'Last updated' is not a real date: {date_match.group(0)}")
        return findings

    if status_date > _dt.date.today():
        findings.append(f"STATUS.md is dated in the future: {status_date.isoformat()}")

    last_change = last_code_commit_date(root, code_paths)
    if is_stale(status_date, last_change):
        findings.append(
            f"STATUS.md is stale: last updated {status_date.isoformat()}, "
            f"but code changed {last_change.isoformat()} "
            f"(paths: {', '.join(code_paths)})"
        )

    if strict:
        dirty = dirty_paths(root)
        if dirty is not None:
            code_dirty = [
                p for p in dirty
                if any(p == c or p.startswith(c + "/") for c in code_paths)
            ]
            if code_dirty and "STATUS.md" not in dirty:
                findings.append(
                    "code is modified but STATUS.md is not in the diff: "
                    + ", ".join(sorted(code_dirty)[:5])
                )

    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail when STATUS.md has gone stale.")
    ap.add_argument("root", nargs="?", type=Path, default=Path("."))
    ap.add_argument("--strict", action="store_true",
                    help="also require STATUS.md in the diff when code is dirty")
    ap.add_argument("--path", action="append", dest="paths", metavar="DIR",
                    help="code path to watch, repeatable (default: %s)"
                         % " ".join(DEFAULT_CODE_PATHS))
    args = ap.parse_args(argv)

    root = args.root.resolve()
    paths = args.paths or DEFAULT_CODE_PATHS
    findings = check(root, paths, strict=args.strict)

    if findings:
        print("FAIL - STATUS.md:", *findings, sep="\n  ", file=sys.stderr)
        return 1
    print(f"OK - STATUS.md is current ({root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
