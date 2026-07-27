# gitbrief Changelog

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
