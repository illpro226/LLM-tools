# sgrep Testing

Fixture-based, per repo conventions (AGENTS.md). Tests exercise the condenser
against a real `rg` where available and against canned `rg --json` streams so
CI never depends on match behavior drift.

## Fixtures

- `tests/fixtures/tree/` — source tree with `src/`, `tests/`, and a generated
  dir; one file with >5 near-identical matches; files with known match
  densities for ranking assertions.
- `tests/fixtures/rg-output/*.jsonl` — canned `rg --json` event streams for
  parser tests.

## Test areas

- **Parsing** — canned JSON streams parse to the expected hit lists,
  incrementally (no full-buffer requirement).
- **Grouping and dedupe** — per-file counts correct; a file with >5 matches
  shows exactly 3 distinct representatives (normalized-content dedupe) plus a
  correct `(+N more similar)` note.
- **Ranking** — density × path-class ordering: src before tests before
  generated; config override changes class weights; ties break by path sort.
- **Cheap modes** — `--files-only` and `--counts-only` formats.
- **Token cap** — at descending budgets, reduction order is context lines →
  matches per file → files shown; output within budget at each step.
- **Missing ripgrep** — with `rg` absent from PATH (patched env), a short
  install-hint error and nonzero exit.

## Running

`python -m pytest` from `tools/sgrep/`. Tests that invoke real `rg` skip with
a notice when it is not installed; parser tests always run.
