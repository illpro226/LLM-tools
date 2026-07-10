# repoindex Testing

Fixture-based, per repo conventions (AGENTS.md). This tool's fixture repo is
shared downstream — `callgraph`, `rq`, and `testmap` test against the same
tree — so it deliberately contains every relationship kind.

## Fixtures

- `tests/fixtures/repo/` — Python, JS/TS, and Go sources containing, with
  known ground truth: functions/classes/methods/consts/types (exported and
  private), calls (including a cycle and a dynamic/duck-typed call), reads,
  writes, type-uses, imports with aliases, an inheritance chain, a
  protocol/interface implementation, convention- and import-linked tests,
  an ambiguous bare name, and a known-dead symbol.

## Test areas

- **Per-table extraction** — after `build`, each table (`files`, `symbols`,
  `refs`, `imports`, `inherits`, `implements`, `tests`) contains exactly the
  expected rows for each language; line spans and visibility flags correct.
- **Resolution** — imported and scope-local references get
  `confidence=resolved`; the dynamic call is stored with
  `confidence=heuristic`, not dropped.
- **Incremental update** — touch one file: only it is re-extracted (parse spy
  proves the untouched file is not re-parsed); rows replaced atomically in
  one transaction; hash short-circuits when mtime changes but content
  doesn't.
- **status** — freshness verdict and per-language file/symbol counts.
- **sql** — read-only: SELECT works with column-aligned output; INSERT/
  UPDATE/DELETE rejected with a short error.
- **Library surface** — `repoindex.extract` parses a standalone (path,
  source) pair without touching the database — the `codediff` contract.
- **Housekeeping** — `.repoindex/` present in `.gitignore` after build.
- **Determinism** — two builds of the same tree produce identical table
  contents (stable IDs/ordering).

## Running

`python -m pytest` from `tools/repoindex/`.
