# xread Status

Implemented (v0.4.1) and passing tests. A call with no mode flag defaults to
`--headings` (v0.4.1) rather than erroring.

- `xread.py` — single-file CLI covering all PRD modes plus the markdown mode
  from repo ADR-0001: `--symbol` (nested names, markdown sections),
  `--lines [--scope]`, `--query` (top-scoring blocks), `--headings`
  (markdown outline, or a code file's symbols with their spans). Citable `== path:start-end ==` headers, elision
  markers, overlap merging, multi-file grouping, `--max-tokens` (drop
  lowest-score blocks, then trim at blank-line boundaries).
- Parsers (stdlib only — ADR-004 deviation from the planned tree-sitter):
  Python via `ast` (exact spans, decorators + attached comments), JS/TS via
  a brace-tracking line scanner (heuristic: declarations must open their
  brace on the same line), markdown via fence-aware heading scan, Prisma
  schemas via a flat block scanner (model/enum/type/view/generator/
  datasource, attached `//` comments).
- Query mode pulls a short fenced sibling section into a markdown match
  that starts at a heading (the payload-above-the-match case).
- `--max-tokens` defaults to 2000 rather than unbounded (docs/decisions/0005);
  `--max-tokens 0` restores unbounded output.
- Tests: `tests/test_xread.py` (41 tests) against fixtures in
  `tests/fixtures/` (sample.py, sample.ts, doc.md, rank.md, api.md,
  schema.prisma, generated big.py).

Not done / later: no packaging or PATH install story; TS parser does not
handle Allman-style braces or multi-line arrow parameter lists; no
tree-sitter upgrade path wired (would slot in as an alternate parser).
