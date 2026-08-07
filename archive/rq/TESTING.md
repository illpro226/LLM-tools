# rq Testing

Fixture-based, per repo conventions (AGENTS.md). Runs against the shared
`repoindex` fixture repo — which deliberately contains a known import cycle,
a known-dead symbol, an inheritance chain, an interface implementation, and
tagged test rows — plus a hand-seeded database for unit tests.

## Fixtures

- The shared `repoindex` fixture repo with a pre-built index.
- A hand-seeded SQLite file matching the schema for renderer/plumbing unit
  tests without parsing.

## Test areas

- **whouses** — inbound refs grouped by kind (call/read/type-use), complete
  against ground truth, `path:line` per row.
- **implements / inherits** — indented trees match the fixture hierarchy;
  multi-level chains render at correct depths; cycle-safe.
- **impact** — transitive closure includes indirect dependents and
  inheritance-propagated ones; `--depth` caps expansion; output terminates
  with covering tests from the `tests` table.
- **publicapi** — exported symbols with signatures; path-prefix filtering.
- **deadcode** — the known-dead symbol found; exported symbols excluded
  unless `--include-exported`; confidence caveat printed when heuristic refs
  exist.
- **findcycles** — the known import cycle reported; smallest cycles first;
  acyclic subgraph produces none.
- **untested** — public symbols lacking `tests` rows; a coverage-tagged row
  removes its symbol from the list.
- **Shared plumbing** — stale index triggers `repoindex update` (subprocess
  spy); `--json` parses and mirrors text content; `--max-tokens` collapses
  leaf lists to `(+N more)` counts first; every text line carries
  `path:line`; ordering deterministic across runs.

## Running

`python -m pytest` from `tools/rq/`. Integration tests require the
`repoindex` CLI; unit tests run on the seeded database alone.
