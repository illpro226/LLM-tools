# rq PRD

## Problem statement

Once `.repoindex/index.db` exists, a family of high-value repository questions — who uses this, what implements that, what breaks if I change this — becomes almost free: each is one or two SQL queries plus formatting. `rq` ("repo query") ships them as subcommands of one thin CLI so the marginal question costs ~20 lines to add.

## Target users

- Coding agents asking relationship questions before making changes.
- Humans auditing API surface, dead code, cycles, and test coverage gaps.

## Scope

### Subcommands

- `rq whouses SYMBOL` — all inbound refs grouped by kind (call/read/type-use), each with `path:line`.
- `rq implements INTERFACE` — all implementations, as an indented tree.
- `rq inherits BASE` — subclass tree.
- `rq impact SYMBOL` — blast radius: transitive closure over inbound refs + inherits, capped by `--depth`, ending with the covering tests from the `tests` table. This is the "what breaks if I change this" tool.
- `rq publicapi [PATH]` — exported symbols with signatures.
- `rq deadcode` — symbols with zero inbound refs, clearly flagging that heuristic/dynamic refs lower confidence; `--include-exported` off by default.
- `rq findcycles` — SCCs over the module import graph, smallest cycles first.
- `rq untested` — public symbols with no `tests`-table coverage.

### Shared plumbing

- Auto-run `repoindex update` before answering.
- Every subcommand takes `--max-tokens N` (collapse leaf lists to counts first) and `--json`.
- Every output line carries `path:line`.
- Each subcommand stays a small function returning rows from one or two SQL queries.

## Non-goals

- Parsing source or building index data (that is `repoindex`).
- Call-tree exploration UX (that is `callgraph`; `rq` covers the remaining question family).
- Guaranteed-sound dead-code detection; results are labeled with confidence caveats.

## Acceptance criteria

- Each subcommand returns correct results against the same fixture repo `repoindex` uses, including a known import cycle (`findcycles`) and a known-dead symbol (`deadcode`).
- `impact` respects `--depth`, includes inherited dependents, and ends with covering tests.
- `deadcode` excludes exported symbols unless `--include-exported`, and prints the confidence caveat.
- A stale index is refreshed automatically before answering.
- `--json` parses cleanly; `--max-tokens` collapses leaf lists to counts first; every line carries `path:line`.
- Output ordering is deterministic across runs.
