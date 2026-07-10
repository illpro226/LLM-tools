# repomap Changelog

- 2026-07-07: v0.1.0 — initial implementation. Single-file stdlib CLI:
  pruned tree (+ root `.gitignore` subset), top-level symbol outlines for
  Python/JS/TS/Go/Rust/C-C++ plus a generic fallback, identifier-occurrence
  ranking, `--focus`, `--max-tokens` staged degradation (collapse tree →
  drop outlines → drop signatures → tree-only). 18 fixture tests.
  ADR-004 (stdlib parsers, no tree-sitter), ADR-005 (index ranking deferred).
- 2026-07-06: Added initial documentation scaffold.
