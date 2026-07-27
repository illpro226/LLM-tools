# rq Changelog

- 2026-07-27: stdout pinned to UTF-8 so non-ASCII symbol names and paths
  survive a cp1252 console (suite-wide fix).
- 2026-07-11: v0.1.2 — the freshness guard passes the `shutil.which()`-
  resolved path to `subprocess` instead of the bare command name: on
  Windows the PATH entry for `repoindex` is a `.cmd` shim, which
  `CreateProcess` won't resolve from a bare name, so every `rq` query
  crashed with `FileNotFoundError` precisely when the suite was installed
  on PATH as intended. Same fix applied to testmap v0.1.1 and codediff
  v0.1.1. 41 tests.
- 2026-07-10: v0.1.1 — shared flags (`--root`, `--json`, `--max-tokens`,
  `--repoindex`, `--no-update`) are now accepted before the subcommand as
  well as after it; when given in both positions the post-subcommand value
  wins (fixes known-issue `rq-shared-flags-position`; 41 tests).
- 2026-07-09: v0.1.0 — implemented `rq.py` (whouses, implements, inherits,
  impact, publicapi, deadcode, findcycles, untested) with the automatic
  freshness guard, `--json`, `--max-tokens` leaf collapse, and 39 tests
  against the shared repoindex fixture repo plus a hand-seeded database.
  Added `py/cyc_a.py`/`py/cyc_b.py` to the repoindex fixture (an import
  cycle for `findcycles`). ADR-001..004 confirmed (ADR-003 amended:
  per-level SQL BFS instead of a recursive CTE); ADR-005 (token budget) and
  ADR-006 (publicapi has no signatures to print) recorded.
- 2026-07-06: Added initial documentation scaffold.
