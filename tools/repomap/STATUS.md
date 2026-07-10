# repomap Status

Implemented (v0.1.0) and passing tests.

- `repomap.py` — single-file, stdlib-only CLI covering the PRD surface:
  pruned tree (built-in skip list + root `.gitignore` subset), per-file
  top-level symbol outlines with signatures and docstring/comment first
  lines, reference-count ranking (most-referenced files first), `--focus
  PATH` (full detail in the subtree, names-only outlines and a shallower
  tree elsewhere), `--max-tokens N` (bytes/4) degrading in order: collapse
  deep tree levels, drop low-rank file outlines, drop signatures,
  tree-only. Never truncates mid-entry.
- Extraction (stdlib only — ADR-004 deviation from the planned
  tree-sitter): Python via `ast`; JS/TS and C/C++ via depth-tracking line
  scanners; Go and Rust via column-0 declaration patterns; other languages
  via a generic declaration regex. Non-Python extraction is
  top-level-only and heuristic by design.
- Ranking is the built-in identifier-occurrence counter only; preferring
  `.repoindex/index.db` is deferred until repoindex pins its schema
  (ADR-005). The ranker function is the seam where it slots in.
- Tests: `tests/test_repomap.py` (18 tests) against the multi-language
  fixture repo in `tests/fixtures/repo/` (Python, TS, Go, Rust, C, Lua
  fallback, vendored/generated/gitignored dirs).

Not done / later: no packaging or PATH install story; nested `.gitignore`
files and negation patterns unsupported; JS/TS declarations must open
their brace on the same line; indented (module-nested) Go/Rust items and
Allman-style C prototypes split across lines are missed.
