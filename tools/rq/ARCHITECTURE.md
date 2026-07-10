# rq Architecture

Status: planned — no implementation exists yet. This describes the intended design.

## Overview

`rq` is a subcommand-per-question dispatcher over `.repoindex/index.db`. The
design goal is that the marginal question costs ~20 lines: each subcommand is a
small function returning rows from one or two SQL queries, with all shared
concerns (freshness, budget, JSON, citations) handled by common plumbing.

```
dispatch(subcommand) ──► ensure fresh index ──► query fn ──► rows
rows ──► shared renderer (text tree/list | --json) under --max-tokens
```

## Components

- **Shared plumbing** — one module providing: the freshness guard (auto
  `repoindex update`), read-only DB handle, `--max-tokens` reduction (collapse
  leaf lists to `(+N more)` counts first), `--json` serialization, and the rule
  that every text line carries `path:line`.
- **Query functions** (one per subcommand):
  - `whouses SYMBOL` — inbound `refs` grouped by kind (call/read/type-use).
  - `implements INTERFACE` / `inherits BASE` — recursive walk over the
    `implements`/`inherits` tables, rendered as an indented tree.
  - `impact SYMBOL` — transitive closure over inbound refs + inherits
    (recursive CTE, capped by `--depth`), terminated with covering tests from
    the `tests` table. The "what breaks if I change this" answer.
  - `publicapi [PATH]` — exported symbols with signatures, filtered by path
    prefix.
  - `deadcode` — symbols with zero inbound refs; prints the confidence caveat
    (heuristic/dynamic refs lower certainty); `--include-exported` off by
    default.
  - `findcycles` — Tarjan SCCs over the module import graph (edges from
    `imports`), smallest cycles first.
  - `untested` — public symbols with no `tests`-table row.
- **Renderers** — a list renderer (grouped rows) and a tree renderer (indented,
  cycle-safe) shared across subcommands.

## Key decisions

- Language: Python, stdlib `sqlite3`; graph work (closure, SCC) done in SQL
  recursive CTEs where natural, in-process for Tarjan.
- No parsing here, ever — data gaps are `repoindex`'s to fix.
- Subcommands stay flat functions; if one grows past ~50 lines it is a smell
  that logic belongs in the index or the shared plumbing.

## Dependencies

Stdlib (`sqlite3`); `repoindex` CLI on PATH at runtime.
