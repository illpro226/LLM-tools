# testmap Testing

Fixture-based, per repo conventions (AGENTS.md). The core fixture is a repo
with *known* import relationships so every mapping layer has a ground truth.

## Fixtures

- `tests/fixtures/repo/` — Python, TS, and Go sources with:
  - convention pairs: `py/foo.py`/`tests_py/test_foo.py` (no import — pure
    convention), `ts/bar.ts`/`ts/bar.spec.ts` (also imports — repoindex
    seeds it as the import link), `go/mathutil/mathutil{,_test}.go`;
  - the import chain `chain_a → chain_b → chain_c` with
    `test_chain_a.py` importing only `chain_a`, for depth assertions;
  - `test_integration.py`, which imports `foo` without being named after
    it — a pure import-depth-1 link;
  - framework config files (pytest.ini, package.json with vitest, go.mod).
- Each test builds a private index with the sibling repoindex checkout
  (`repo` fixture); coverage rows are seeded by SQL or by a real `record`
  run.

## Test areas

- **Convention/import layers** — every fixture pair found with the right
  tag; two-hop change found at default `--depth 2`, excluded at
  `--depth 1`; three-hop change needs `--depth 3`.
- **Coverage layer** — seeded coverage rows outrank convention and import
  tags; `record -- pytest` (requires coverage.py, `importorskip`-guarded)
  writes `source=coverage` rows including runtime-only transitive coverage,
  replaces stale rows for seen test files, and beats the depth limit
  afterwards; non-pytest commands are rejected with exit 2.
- **Change detection** — modified + untracked picked up in a temp git repo;
  clean tree reports "no changed files"; an enclosing repo above `--root`
  is not mistaken for the work tree (exit 1); explicit args bypass git.
- **Changed test file** — selects itself (`changed-test`) and joins the
  run command.
- **Freshness guard** — a file added after the index was built is mapped
  because the lookup runs `repoindex update` first.
- **Output** — deterministic ordering; unmapped indexed files noted;
  `--max-tokens` collapses targets but keeps run commands; `--json`
  mirrors the text; no index exits 2.
- **Unit** — coverage context→test-file attribution across the dotted,
  `path::node`, ambiguous, and empty context shapes.

## Running

`python -m pytest` from `tools/testmap/` (pytest.ini keeps collection out
of `tests/fixtures/`). Requires `git`; the `record` test additionally
requires coverage.py and self-skips without it.
