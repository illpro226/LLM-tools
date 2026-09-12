#!/usr/bin/env python3
"""Fail when AGENTS.md describes an environment that is not this one.

The Commands block is the first thing a cold agent trusts, and a command whose
tool is not installed costs a failed call plus a discovery detour - exactly the
tax the root file exists to remove. This is the check that can return "no".

    python scripts/check_env.py [root]

Checks, in order:
  1. AGENTS.md has a non-empty '## Environment' section with no placeholders.
  2. Every executable named in the Commands block resolves on PATH.
  3. Every repo-relative path operand in those commands exists.

Stdlib only. Exit 0 clean, 1 on any finding.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
HEADING_RE = re.compile(r"^#{1,6}\s+(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*```")
COMMAND_RE = re.compile(r"^([a-z][a-z0-9_-]*):\s+(.*?)\s*$")

# A value that is honestly absent. Neither is a command, so neither is checked.
NOT_A_COMMAND = ("TODO", "(none")

# Shell builtins are not programs and never resolve on PATH. `cd backend &&
# npm test` is the ordinary shape of a command in any multi-package repo, so
# treating `cd` as a missing tool would fail every monorepo that exists.
SHELL_BUILTINS = {
    "cd", "export", "set", "unset", "source", ".", "exec", "eval",
    "true", "false", ":", "alias", "umask", "pushd", "popd",
}

# Segment separators. Each segment runs its own program and is checked.
SEGMENT_RE = re.compile(r"&&|\|\||;|\|")


def heading_key(heading: str) -> str:
    """The heading's subject, with any trailing gloss dropped.

    Headings in this file carry an explanatory tail ("Environment - what a cold
    agent would otherwise have to discover"); the subject identifies
    the section."""
    text = re.split("\\s+[-\u2013\u2014:]\\s+", heading.strip(), maxsplit=1)[0]
    return " ".join(text.lower().split())


def environment_block(body: str) -> list[str] | None:
    """Lines of the '## Environment' section, or None if there is no such
    section. Comments and blanks dropped, so an empty section reads as empty."""
    out: list[str] | None = None
    inside = False
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            inside = heading_key(m.group(1)) == "environment"
            if inside:
                out = []
            continue
        if not inside or out is None:
            continue
        text = line.strip()
        if not text or text.startswith("<!--") or FENCE_RE.match(line):
            continue
        out.append(text)
    return out


def command_lines(body: str) -> list[tuple[str, str]]:
    """(label, command) for every 'label: command' line inside a fenced block.

    Fenced, because prose elsewhere in the file uses the same colon shape and
    is not meant to be run."""
    out: list[tuple[str, str]] = []
    fenced = False
    for line in body.splitlines():
        if FENCE_RE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            continue
        m = COMMAND_RE.match(line)
        if m and not m.group(2).startswith(NOT_A_COMMAND):
            out.append((m.group(1), m.group(2)))
    return out


def executable(command: str) -> str | None:
    """The program a command segment invokes, or None if there isn't one.

    Leading VAR=value assignments are environment, not the program."""
    for token in command.split():
        if "=" in token.split("/")[0]:
            continue
        return token
    return None


def programs(command: str) -> list[str]:
    """Every program a command actually runs, builtins excluded.

    A command is commonly a chain - `cd backend && npm install && npm test`.
    Checking only the first token would check `cd` and miss `npm` entirely."""
    out = []
    for segment in SEGMENT_RE.split(command):
        exe = executable(segment)
        if exe is None or exe in SHELL_BUILTINS:
            continue
        out.append(exe)
    return out


def path_operands(command: str) -> list[str]:
    """Operands that name a file in this repo. Flags, globs and package specs
    (`./...`, `src/**`) are deliberately excluded - they are not lookups."""
    out = []
    for token in command.split()[1:]:
        if token.startswith("-") or "=" in token or "*" in token:
            continue
        if "/" not in token or token.endswith("..."):
            continue
        out.append(token)
    return out


def check(root: Path, which=shutil.which) -> list[str]:
    """Return one line per finding. `which` is injected so the rule is
    testable without depending on what happens to be installed."""
    findings: list[str] = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return ["AGENTS.md is missing"]

    body = agents.read_text(encoding="utf-8")

    block = environment_block(body)
    if block is None:
        findings.append(
            "AGENTS.md has no 'Environment' section - an agent cannot know "
            "which interpreter to use, or what is enforced for it"
        )
    elif not block:
        findings.append(
            "AGENTS.md section 'Environment' is empty - 'nothing special' is a "
            "claim worth writing, silence is not"
        )
    else:
        for line in block:
            for m in PLACEHOLDER_RE.finditer(line):
                findings.append(
                    f"AGENTS.md 'Environment' still holds an unresolved "
                    f"placeholder: {m.group(1)}"
                )

    for label, command in command_lines(body):
        found = programs(command)
        if not found:
            findings.append(f"command '{label}' names no program: {command}")
            continue
        for exe in found:
            if which(exe) is None:
                findings.append(
                    f"command '{label}' needs '{exe}', which is not on PATH: {command}"
                )
        for operand in path_operands(command):
            if not (root / operand).exists():
                findings.append(
                    f"command '{label}' points at a path that does not exist: {operand}"
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check AGENTS.md against this machine.")
    ap.add_argument("root", nargs="?", default=".", type=Path)
    args = ap.parse_args(argv)

    root = args.root.resolve()
    findings = check(root)
    if findings:
        print("FAIL - AGENTS.md does not match this environment:",
              *findings, sep="\n  ", file=sys.stderr)
        return 1
    print(f"OK - {root.name}: environment stated, commands runnable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
