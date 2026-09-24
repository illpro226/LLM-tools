# repomap Changelog

- 2026-09-24: v0.4.0 — fixes from a suite review, each pinned by a test
  that fails on v0.3.0 (the ranking test pins equality with the old
  scores instead).
  **The ladder did not terminate on a wide directory.** Tree-only
  collapsed depth, which never shrinks a directory's own listing: a root
  of 3,000 files printed ~12,800 tokens against the 3,000 default, under a
  note claiming the budget. ADR-008 adds a last rung that lists at most N
  entries per directory (the largest N that fits) and counts the rest.
  **Ranking was O(files²).** Each file's score walked every other file:
  3.3 s of a 12 s run over Python's 1,853-file stdlib. Scores now come
  from identifier document frequencies — identical numbers (pinned against
  the pairwise count on the fixture and the whole suite), linear time.
  **A BOM'd Python file outlined as empty**, and defs under module-level
  `if`/`try`/`with` (platform splits, ImportError fallbacks) were missing.
  Files are read as `utf-8-sig`; those blocks are walked.
  **JS/TS depth drifted after a multi-line template literal**: the line
  holding the closing backtick was skipped whole, so a `{` after it never
  opened and a nested declaration read as top-level.
  4 new tests (29 total).
- 2026-07-31: v0.3.0 — `--max-tokens` now defaults to 3000 instead of unbounded
  (ADR-007, docs/decisions/0005-budgets-on-by-default.md); `--max-tokens 0`
  restores the old behaviour. `repomap .` on this repo drops from ~15,000
  to ~2,900 tokens with no flag passed. 4 new tests (25 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
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
