# rq Roadmap

Depends on `repoindex` M1–M3; shares its fixture repo (including the known
cycle and known-dead symbol).

## M1 — Plumbing and first queries

- Dispatcher, freshness guard, read-only DB handle, shared renderers.
- `whouses` (grouped by ref kind) and `publicapi`.

## M2 — Hierarchy and impact

- `implements` and `inherits` indented trees.
- `impact` recursive closure with `--depth`, ending with covering tests.

## M3 — Hygiene queries

- `deadcode` with confidence caveat and `--include-exported` gate.
- `findcycles` (SCCs, smallest first) and `untested`.

## M4 — Output contract

- `--json` and `--max-tokens` (leaf-collapse first) across all subcommands;
  `path:line` on every line; determinism tests.

## Later

- Next questions as they prove valuable (`rq owners`, `rq hotspots`, …) —
  each should stay ~20 lines.
