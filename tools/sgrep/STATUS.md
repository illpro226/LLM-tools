# sgrep Status

Implemented (v0.4.0) and passing tests.

- `sgrep.py` — single-file CLI covering all PRD modes: condensed ranked
  digest, `--files-only`, `--counts-only`, `--no-collapse`,
  `--max-tokens` (ADR-003 order:
  context lines → matches per file → files shown, converging to counts).
- Wraps `rg --json --sort path` (ADR-001); binary resolved from PATH,
  `--rg`, or `SGREP_RG`. Missing binary is a clear install-hint error
  (exit 2); no matches exits 1 like grep.
- Dedupe (ADR-002): matches cluster by normalized text (whitespace
  collapsed, digit runs → 0); >5 matching lines shows 3 representatives
  plus `(+N more similar)`. `--no-collapse` turns clustering off for
  exhaustive "edit each of these" work; the token budget still applies and
  announces itself when it caps.
- Ranking: match count × path-class weight (src 1.0 / tests 0.5 /
  generated 0.2), overridable via `.sgrep.toml` (`[weights]`, extra
  `[classes]` fnmatch patterns); ties break by path.
- `--max-tokens` defaults to 1500 rather than unbounded (docs/decisions/0005);
  `--max-tokens 0` restores unbounded output.
- Output format: match lines carry `path:line:`; `-C` context lines carry a
  bare right-aligned line number under the block header that names the file
  (INVARIANTS.md). Measured -23% output on context searches, and the reason
  sgrep stopped being the one suite tool that often printed more than the
  raw `rg` it replaced.
- Tests: `tests/test_sgrep.py` (32 tests) — parser/dedupe/rank/budget
  against canned `rg --json` streams in `tests/fixtures/rg-output/`;
  5 end-to-end tests run against real ripgrep and skip when absent.

Not done / later: no packaging or PATH install story; stored matches capped
at 200/file (count keeps rising); budgets under ~32 tokens are unsatisfiable
and floor at one row + elision marker.
