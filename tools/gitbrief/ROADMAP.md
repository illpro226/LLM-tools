# gitbrief Roadmap

## M1 — Scaffold and default view — done (v0.1.0)

- CLI entry point; test harness that builds temp repos.
- Git runner over porcelain formats; branch, drift, status+diffstat table,
  last-5-commits view.

## M2 — Drill-down modes — done (v0.1.0)

- `hunks [FILE...]` with 1-context-line headers.
- `show FILE` full single-file diff.
- `log --grep/--author/-n` condensed history.

## M3 — Branch summary — done (v0.1.0, stdlib symbols; ADR-005)

- `pr BASE`: merge-base diffstat + commit list.
- Changed-symbol list via stdlib extraction of before/after blobs
  (Python + JS/TS; the optional-tree-sitter plan is superseded).

## M4 — Token budget — done (v0.1.0)

- `--max-tokens N` reduction rules per mode, tested in temp repos at
  descending budgets.

## Later

- Stash/worktree awareness in the default view if it proves useful.
