# xread Status

Implemented (v0.5.0) and passing tests. A call with no mode flag defaults to
`--headings` (v0.4.1) rather than erroring.

- `xread.py` — single-file CLI covering all PRD modes plus the markdown mode
  from repo ADR-0001: `--symbol` (nested names, markdown sections),
  `--lines [--scope]`, `--query` (top-scoring blocks), `--headings`
  (markdown outline, or a code file's symbols with their spans). Citable `== path:start-end ==` headers, elision
  markers, overlap merging, multi-file grouping, `--max-tokens` (drop
  lowest-score blocks, then trim at blank-line boundaries).
- Parsers (stdlib only — ADR-004 deviation from the planned tree-sitter):
  Python via `ast` (exact spans, decorators + attached comments; defs and
  constants under module/class-level `if`/`try`/`with` count), JS/TS via
  a brace-tracking line scanner (heuristic: declarations must open their
  brace on the same line), markdown via a CommonMark fence-aware heading
  scan (a fence closes only on the same character, at least as long), Prisma
  schemas via a flat block scanner (model/enum/type/view/generator/
  datasource, attached `//` comments).
- Query mode pulls a short fenced sibling section into a markdown match
  that starts at a heading (the payload-above-the-match case).
- `--max-tokens` defaults to 2000 rather than unbounded (docs/decisions/0005);
  `--max-tokens 0` restores unbounded output. An over-budget `--headings`
  hides the deepest entries first, so the outline still spans the file,
  and truncates the top level only as the last rung.
- Files are read as `utf-8-sig`, so a byte-order mark no longer breaks the
  Python parse or hides a line-1 JS declaration.
- Tests: `tests/test_xread.py` (61 tests) against fixtures in
  `tests/fixtures/` (sample.py, sample.ts, doc.md, rank.md, api.md,
  schema.prisma, generated big.py).

Not done / later: no packaging or PATH install story; TS parser does not
handle Allman-style braces or multi-line arrow parameter lists; no
tree-sitter upgrade path wired (would slot in as an alternate parser).
