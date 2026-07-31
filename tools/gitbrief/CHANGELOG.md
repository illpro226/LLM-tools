# gitbrief Changelog

- 2026-07-31: v0.2.1 — git repository discovery is bounded by
  `GIT_CEILING_DIRECTORIES`, defaulted to `$HOME` (ADR-007). Without it, a
  run outside any project walked up to a home directory that is itself a
  repo and scanned the whole tree — a multi-minute hang, not an error.
  Repos below `$HOME` are unaffected; `GITBRIEF_NO_CEILING=1` or your own
  `GIT_CEILING_DIRECTORIES` overrides. 4 new tests (30 total).
- 2026-07-31: v0.2.0 — `--max-tokens` now defaults to 2000 instead of unbounded
  (ADR-006, docs/decisions/0005-budgets-on-by-default.md); `--max-tokens 0`
  restores the old behaviour. `gitbrief hunks` on this repo's working diff
  drops from ~2,900 to ~310 tokens with no flag passed. 4 new tests
  (26 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
- 2026-07-27: v0.1.1 — stdout pinned to UTF-8 so echoed file content keeps
  its non-ASCII characters on Windows. Closes the gitbrief half of
  docs/known-issues/non-ascii-output-mangled-on-windows.md.
- 2026-07-08: v0.1.0 — initial implementation. Single-file stdlib CLI over
  git plumbing: default status+diffstat view with drift and last commits,
  `hunks` (U1), `show` (single-file full diff), `log` filters, `pr BASE`
  with stdlib changed-symbol lists (Python/JS-TS). `--max-tokens` staged
  degradation per mode; read-only enforced (`--no-optional-locks`,
  snapshot-tested). 20 temp-repo tests. ADR-005 (stdlib symbol extraction
  supersedes optional tree-sitter).
- 2026-07-06: Added initial documentation scaffold.
