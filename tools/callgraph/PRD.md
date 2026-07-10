# callgraph PRD

## Problem statement

Agents discover call relationships manually: grep for a name, read three files, grep again — an expensive loop repeated many times per task. `callgraph` answers "what does X call, and what calls X" in one shot, with citable locations, as a pure query over the shared `repoindex` database.

## Target users

- Coding agents tracing how a symbol is used before changing it.
- Humans exploring unfamiliar code paths.

## Scope

### Core behavior

- `callgraph SYMBOL` resolves dotted/qualified names and bare names; if multiple symbols match a bare name, print a disambiguation list.
- Output: where the symbol is defined (`path:line`), its direct callees with locations, and its callers with locations.
- `--depth N` expands the tree in either direction (`--callers` / `--callees`; default both at depth 1), with cycle detection (`(cycle)` marker) and per-node dedup.

### Implementation constraints

- Pure query layer over `.repoindex/index.db`: walk the `refs` table (kind=call) joined against `symbols`. Do not parse source directly.
- If the index is missing or stale, run `repoindex update` automatically first.
- Surface the index's confidence column: mark dynamic/duck-typed call edges with `?`.

### Output conventions

- Every line carries a `path:line` reference so an agent can jump straight to `xread`.
- `--max-tokens N`: shrink by reducing depth, then collapsing sibling lists to counts.

## Non-goals

- Parsing or indexing source itself (that is `repoindex`).
- Non-call relationships like reads/writes/type-use (that is `rq whouses`).
- Whole-program soundness for dynamic dispatch; heuristic edges are shown, marked `?`.

## Acceptance criteria

- On the fixture repo with known call relationships: definition, callees, and callers are all correct with `path:line` on every row.
- A bare ambiguous name produces a disambiguation list; a qualified name resolves directly.
- `--depth 2 --callers` expands correctly; the fixture cycle is marked `(cycle)` and traversal terminates.
- Heuristic-confidence edges appear with `?`.
- With a stale/missing index, the tool triggers `repoindex update` and then answers.
- `--max-tokens` reduces depth first, then collapses siblings to counts.
