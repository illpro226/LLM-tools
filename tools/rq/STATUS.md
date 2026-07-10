# rq Status

Implemented (v0.1.0) and passing tests.

- `rq.py` — single-file stdlib CLI over `.repoindex/index.db`. Eight
  subcommands: `whouses`, `implements`, `inherits`, `impact`, `publicapi`,
  `deadcode`, `findcycles`, `untested`.
- Shared plumbing: an automatic `repoindex update` before every query
  (`--no-update` skips; the binary resolves via `--repoindex`, `RQ_REPOINDEX`,
  PATH, then the sibling checkout `tools/repoindex/repoindex.py`), read-only
  DB access (`mode=ro` URI), `--json` mirroring the text content,
  `--max-tokens` collapsing leaf lists to `(+N more)` counts (ADR-005),
  `path:line` on every claim line, deterministic ordering throughout.
- Symbol matching is case-sensitive (`substr()` suffix comparisons, not
  `LIKE`, which is ASCII case-insensitive) and accepts a full qualname, a
  local name (`Rectangle`), or a member name (`area`); raw parent/interface
  names from `inherits`/`implements` match within one language family
  (javascript+typescript count as one).
- `impact` runs a per-level SQL BFS rather than a recursive CTE (ADR-003 as
  amended) over inbound refs plus inherits/implements edges, labels refs not
  enclosed by any symbol span "(module level)", caps at `--depth` (default
  3), and terminates with the covering tests of every affected file.
- `deadcode` is conservative by default (ADR-004): exported symbols need
  `--include-exported`; dunders, test-file symbols, heuristic name matches,
  inherits-parents, and implements-interfaces are excluded; a caveat notes
  how many heuristic refs could hide callers.
- `findcycles` matches import module strings to file stems per language
  family (same-directory candidates win), then runs iterative Tarjan SCC;
  cycles print smallest first.
- Exit codes: 0 success, 1 symbol not found, 2 no index and repoindex
  unavailable.
- Tests: `tests/test_rq.py` (39 tests) against the shared repoindex fixture
  repo (built via the repoindex package) plus a hand-seeded database
  (inheritance cycle, external base, two import cycles of different sizes,
  a coverage-tagged file). Covers every subcommand's ground truth, the
  freshness guard (subprocess spy and a real end-to-end stale-index run),
  `--json` mirroring, `--max-tokens` collapse and count-only floor, the
  `path:line` audit, and run-twice determinism.

Not done / later: `publicapi` prints kind + location, not signatures — the
index stores none (ADR-006); index-derived data gaps (receiver calls always
heuristic, raw inherits/implements names) are repoindex's to fix (ADR-002);
`callgraph`-style path queries between two symbols remain future work
(ROADMAP.md).
