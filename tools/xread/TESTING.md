# xread Testing

Fixture-based, per repo conventions (AGENTS.md). The PRD requires Python and
TypeScript coverage for all three modes.

## Fixtures

- `tests/fixtures/sample.py` — module with top-level functions, a class with
  methods (nested resolution: `ClassName.method`), decorators, and docstrings.
- `tests/fixtures/sample.ts` — equivalent TypeScript shapes.
- A large file (several hundred lines) for elision and budget cases.

## Test areas

- **Symbol mode** — full body returned for top-level and nested symbols;
  decorators/attached comments included; header is exact
  `path:startline-endline`; unknown symbol yields a short error.
- **Line + scope mode** — a mid-function range expands to the whole enclosing
  function/class; without `--scope` the raw range is returned.
- **Query mode** — top-scoring blocks first; ordering deterministic across
  runs; block boundaries respected (no partial functions).
- **Merging and elision** — overlapping regions merged (no duplicated lines);
  `… N lines elided …` between non-adjacent excerpts with correct N;
  adjacent excerpts joined without a marker.
- **Multi-file** — output grouped per file in argument order.
- **Token cap** — at descending budgets: lowest-score blocks dropped first,
  largest excerpt trimmed at block boundaries; never a mid-statement cut.

## Running

`python -m pytest` from `tools/xread/`.
