# sgrep Roadmap

## M1 — Scaffold and passthrough

- CLI entry point, fixture tree, test harness.
- `rg --json` runner with streaming parse; missing-ripgrep error path.

## M2 — Grouping and dedupe

- Per-file grouping with counts; normalized-content dedupe;
  3-representatives + `(+N more similar)` behavior.

## M3 — Ranking and cheap modes

- Density × path-class ranking with configurable class patterns.
- `--files-only` and `--counts-only`.

## M4 — Token budget

- `--max-tokens N` reducing context → matches → files, tested at
  descending budgets; deterministic tie-breaking test.

## Later

- Config file for path-class weights; `--json` output if a consumer appears.
