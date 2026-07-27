# repomap Changelog

- 2026-07-27: v0.2.0 — `--focus PATH` now narrows instead of merely
  ranking: unfocused files collapse to `path [refs N] (K symbols)` with a
  note. Runs of 3+ `test_*` functions collapse to one counted line, so a
  well-tested file no longer costs more to map. stdout pinned to UTF-8 so
  non-ASCII file content survives a cp1252 console. 21 tests.
  Closes docs/known-issues/repomap-focus-does-not-narrow-output.md and
  the repomap half of non-ascii-output-mangled-on-windows.md.
- 2026-07-07: v0.1.0 — initial implementation. Single-file stdlib CLI:
  pruned tree (+ root `.gitignore` subset), top-level symbol outlines for
  Python/JS/TS/Go/Rust/C-C++ plus a generic fallback, identifier-occurrence
  ranking, `--focus`, `--max-tokens` staged degradation (collapse tree →
  drop outlines → drop signatures → tree-only). 18 fixture tests.
  ADR-004 (stdlib parsers, no tree-sitter), ADR-005 (index ranking deferred).
- 2026-07-06: Added initial documentation scaffold.
