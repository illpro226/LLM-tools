# gitbrief Architecture

Status: implemented (v0.1.0) as a single stdlib-only file, `gitbrief.py`.

## Overview

`gitbrief` is a thin formatting layer over `git` plumbing subprocess calls. Each
mode gathers raw data via a small set of plumbing commands, builds a view model,
and renders it under the token cap. No libgit binding.

```
plumbing calls ──► raw text (porcelain formats)
parse ──► view model (branch, drift, files, commits, hunks, symbols)
fit(levels, budget) ──► most detailed rendering within budget
```

## Components

- **Git runner** (`_git`) — one subprocess helper with explicit argv,
  `--no-optional-locks --no-pager -c color.ui=false -c core.quotepath=false`,
  and stable porcelain formats (`status --porcelain=v2 --branch`,
  `diff --numstat --no-renames`, `log --format=…`, `merge-base`). Every data
  fetch is a reproducible command line; human-oriented output is never parsed.
- **Default view** — branch + upstream drift from the porcelain v2 branch
  headers; merged status+diffstat table (staged/unstaged/untracked with +/-
  per file; untracked line counts are streamed by gitbrief itself); last 5
  commits as one-liners.
- **hunks mode** — `diff HEAD -U1` parsed to per-file hunk lists,
  optionally filtered to named files.
- **show mode** — full diff for exactly one file (the deliberate escape
  hatch); unbudgeted output is byte-identical to `git diff HEAD -- FILE`.
- **log mode** — condensed one-liners with `--grep/--author/-n` passthrough.
- **pr mode** — merge-base vs BASE: diffstat + commit list + changed-symbol
  list. Symbols come from stdlib parses of the before/after blobs
  (`git show REV:path`) for Python and JS/TS, classified
  +added / ~modified / -removed by intersecting symbol spans with `-U0`
  diff ranges (ADR-005; the old optional-tree-sitter plan is superseded).
  Unanalyzed languages are named in a note rather than silently skipped.
- **Budget reducer** (`fit`) — per mode, an ordered list of render levels;
  the first within budget wins: default view collapses the file table to
  counts then trims the commit list; hunks drops context lines, then hunk
  bodies, then everything but per-file counts; log/pr shorten lists (pr
  drops the symbol section first, per-file diffstat rows next — totals and
  the commit count never disappear).

## Key decisions

- Language: Python; subprocess-only git access keeps the tool dependency-free
  and debuggable. Rename detection is off (`--no-renames`) so renames read as
  delete + add with exact counts.
- Porcelain/plumbing formats only — never parse human-oriented git output.
- Read-only: no mode mutates repo state (`--no-optional-locks` keeps even
  `status` from rewriting the index); test-enforced by state snapshots.

## Dependencies

`git` binary at runtime; Python stdlib otherwise.
