# callgraph Testing

Fixture-based, per repo conventions (AGENTS.md). Tests run against the shared
fixture repo used by `repoindex` (which includes a known cycle and an
ambiguous name), querying a pre-built index — plus stubbed-index tests that
don't require repoindex at all.

## Fixtures

- The shared `repoindex` fixture repo with known call relationships: a
  function with multiple callees/callers, a call cycle, two symbols sharing a
  bare name, and a heuristic-confidence (dynamic) call edge.
- A hand-seeded SQLite file matching the schema, for unit tests of traversal
  and rendering without any parsing.

## Test areas

- **Resolution** — qualified names resolve directly; a bare ambiguous name
  prints a disambiguation list (qualname + path:line) and exits without a
  report; unknown symbol errors shortly.
- **Depth-1 report** — definition line, callees, and callers all correct with
  `path:line` on every row.
- **Traversal** — `--depth 2` expansion in both directions; `--callers` /
  `--callees` restrict correctly; the fixture cycle renders `(cycle)` and
  terminates; repeated nodes deduped.
- **Confidence** — the dynamic edge renders with `?`; resolved edges clean.
- **Freshness guard** — with a missing index, `repoindex update` is invoked
  (subprocess spy) before querying; with a stale file hash, likewise.
- **Token cap** — depth reduced first, then siblings collapse to `(+N more)`;
  within budget at descending caps.
- **Determinism** — sibling ordering is (path, line) sorted; identical output
  across runs.

## Running

`python -m pytest` from `tools/callgraph/`. Integration tests require the
`repoindex` CLI; unit tests run against the seeded database alone.
