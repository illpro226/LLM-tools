# testmap Changelog

- 2026-07-06: Added initial documentation scaffold.
- 2026-07-11: v0.1.1 — the freshness guard passes the `shutil.which()`-
  resolved path to `subprocess` instead of the bare command name (Windows
  `.cmd` PATH shims raise `FileNotFoundError` from a bare name; same fix
  as rq v0.1.2 and codediff v0.1.1). 22 tests.
- 2026-07-10: v0.1.0 — implemented map mode (git/explicit changed-file set;
  coverage, changed-test, convention, and depth-limited import layers as a
  union tagged by most-trusted source; per-framework run commands; --json,
  --max-tokens, freshness guard via `repoindex update`) and `record` for
  pytest via coverage.py dynamic contexts (ADR-005..007). The lookup path
  reads only the shared index — no source parsing (ADR-005), superseding
  ARCHITECTURE.md's original parse-the-test-files plan. Companion repoindex
  change: `update` now preserves `source=coverage` rows instead of wiping
  the whole `tests` table. 22 tests.
