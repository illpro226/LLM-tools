# sgrep Status

Implemented (v0.5.0) and passing tests.

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
- Paths are normalized to `/` at the parser, so a directory-scoped
  search and an explicitly-named file report the same file identically
  on Windows (`rg` echoes whichever separator it was given).
- rg's stderr drains concurrently (a full pipe used to hang both
  processes). When rg fails on some paths but matched in others, the
  matches print, the error goes to stderr, and the exit is 2.
- The file-count budget rung is a binary search, so a 20,000-file search
  fits the default budget in ~3 s rather than ~8 minutes; `--files-only`
  announces files the budget cut with the digest's `(+N more files …)`.
- Tests: `tests/test_sgrep.py` (40 tests) — parser/dedupe/rank/budget
  against canned `rg --json` streams in `tests/fixtures/rg-output/`;
  7 end-to-end tests run against real ripgrep and skip when absent.

Not done / later: no packaging or PATH install story; stored matches capped
at 200/file (count keeps rising); budgets under ~32 tokens are unsatisfiable
and floor at one row + elision marker.
