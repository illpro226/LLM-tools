# factbook Architecture

Status: planned — no implementation exists yet. This describes the intended design.

## Overview

`factbook` is a plain-markdown store with a CLI on top. The filesystem is the
database: one file per fact, an INDEX.md of one-liners, no binary state. Humans
and git are first-class writers alongside the CLI.

```
.factbook/
  INDEX.md              # regenerated one-liner per fact
  build-with-make.md    # one fact file
  auth-location.md
  ...
```

## Components

- **Fact file format** — markdown with a small front-matter block (name, tags,
  created, updated) followed by the body. The parser is tolerant: a hand-written
  file with just a title and body is still valid (missing fields defaulted).
- **Store layer** — create/read/update/delete of fact files; slugifies names,
  bumps `updated` on change, regenerates INDEX.md after every mutation so the
  index can never drift silently.
- **Search** (`find`) — keyword + tag matching over names, tags, and bodies with
  simple field-weighted ranking (name > tags > body). Returns one-liners;
  `--full` expands bodies. No embeddings, no external index — repo fact counts
  are small enough that a linear scan is fast.
- **Brief** — prints INDEX.md under `--max-tokens N`, trimming lowest-ranked
  lines (oldest, least-tagged) rather than cutting mid-line. Designed to be
  injected at session start.
- **Stale detector** — extracts path-like tokens from fact bodies and checks
  existence against the working tree; flags facts whose referenced paths are
  gone. Advisory only — nothing is auto-deleted.
- **Edit** — opens `$EDITOR` on the fact file, then re-indexes.

## Key decisions

- Language: Python, stdlib only.
- Plain markdown over SQLite: human editability and git-versionability are the
  product; search speed is a non-problem at realistic fact counts.
- INDEX.md is always derived state — regenerated, never hand-maintained.

## Dependencies

Stdlib only.
