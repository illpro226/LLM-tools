# sgrep Status

Implemented (v0.2.0) and passing tests.

- `sgrep.py` — single-file CLI covering all PRD modes: condensed ranked
  digest, `--files-only`, `--counts-only`, `--max-tokens` (ADR-003 order:
  context lines → matches per file → files shown, converging to counts).
- Wraps `rg --json --sort path` (ADR-001); binary resolved from PATH,
  `--rg`, or `SGREP_RG`. Missing binary is a clear install-hint error
  (exit 2); no matches exits 1 like grep.
- Dedupe (ADR-002): matches cluster by normalized text (whitespace
  collapsed, digit runs → 0); >5 matching lines shows 3 representatives
  plus `(+N more similar)`.
- Ranking: match count × path-class weight (src 1.0 / tests 0.5 /
  generated 0.2), overridable via `.sgrep.toml` (`[weights]`, extra
  `[classes]` fnmatch patterns); ties break by path.
- `--max-tokens` defaults to 1500 rather than unbounded (docs/decisions/0005);
  `--max-tokens 0` restores unbounded output.
- Tests: `tests/test_sgrep.py` (28 tests) — parser/dedupe/rank/budget
  against canned `rg --json` streams in `tests/fixtures/rg-output/`;
  5 end-to-end tests run against real ripgrep and skip when absent.

Not done / later: no packaging or PATH install story; stored matches capped
at 200/file (count keeps rising); budgets under ~32 tokens are unsatisfiable
and floor at one row + elision marker.
