# callgraph Architecture

Status: planned — no implementation exists yet. This describes the intended design.

## Overview

`callgraph` is a pure query layer: it never parses source. All data comes from
`.repoindex/index.db` (`symbols` joined with `refs` where kind=call); the tool's
own work is name resolution, traversal, and rendering.

```
ensure fresh index (repoindex update if missing/stale)
resolve(SYMBOL) ──► symbol row (or disambiguation list)
walk refs (callers | callees, depth N) ──► tree with cycle/dedup marks
render(tree, budget) ──► citable report
```

## Components

- **Freshness guard** — checks index existence and staleness (mtime vs indexed
  hashes) and shells out to `repoindex update` before querying.
- **Resolver** — exact match on qualified name first; bare names match by
  suffix. Multiple hits print a disambiguation list (qualname + `path:line`)
  and exit; a qualified re-query resolves directly.
- **Traversal** — breadth-limited walk over `refs` (kind=call) joined against
  `symbols`, in either direction (`--callers` / `--callees`; default both at
  depth 1). Maintains a visited set for per-node dedup and marks re-entry into
  an ancestor as `(cycle)` instead of recursing.
- **Confidence surfacing** — edges with `confidence=heuristic` (dynamic/
  duck-typed calls) render with a trailing `?`; resolved edges render clean.
- **Renderer** — definition line first (`name  # path:line`), then indented
  `calls:` / `called by:` sections. Every line carries `path:line` so the next
  hop is one `xread` away.
- **Budget reducer** — `--max-tokens N`: reduce depth first, then collapse
  sibling lists to `(+N more)` counts, deepest and lowest-fanout branches first.

## Key decisions

- Language: Python, stdlib `sqlite3` only — the whole tool is a few queries plus
  formatting, which is the payoff of `repoindex` existing.
- No source parsing here, ever; gaps in the graph are fixed in `repoindex`.
- Determinism: sibling ordering is (path, line) sorted.

## Dependencies

Stdlib (`sqlite3`); `repoindex` CLI present on PATH at runtime.
