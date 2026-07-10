# xread Status

Implemented (v0.1.0) and passing tests.

- `xread.py` — single-file CLI covering all PRD modes plus the markdown mode
  from repo ADR-0001: `--symbol` (nested names, markdown sections),
  `--lines [--scope]`, `--query` (top-scoring blocks), `--headings`
  (markdown outline). Citable `== path:start-end ==` headers, elision
  markers, overlap merging, multi-file grouping, `--max-tokens` (drop
  lowest-score blocks, then trim at blank-line boundaries).
- Parsers (stdlib only — ADR-004 deviation from the planned tree-sitter):
  Python via `ast` (exact spans, decorators + attached comments), JS/TS via
  a brace-tracking line scanner (heuristic: declarations must open their
  brace on the same line), markdown via fence-aware heading scan.
- Tests: `tests/test_xread.py` (27 tests) against fixtures in
  `tests/fixtures/` (sample.py, sample.ts, doc.md, generated big.py).

Not done / later: no packaging or PATH install story; TS parser does not
handle Allman-style braces or multi-line arrow parameter lists; no
tree-sitter upgrade path wired (would slot in as an alternate parser).
