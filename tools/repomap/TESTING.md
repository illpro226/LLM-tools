# repomap Testing

Fixture-based, per repo conventions (AGENTS.md): small reproducible inputs,
behavior-named tests, deterministic output assertions.

## Fixtures

- `tests/fixtures/repo/` — a small multi-language repo containing:
  - Python, JS/TS, Go, Rust, and C/C++ source files with known symbols;
  - a file in an unsupported language (regex-fallback path);
  - vendored/generated dirs that must be pruned (`node_modules/`,
    `__pycache__/`, `dist/`);
  - a known reference structure so ranking order is predictable.

## Test areas

- **Pruning** — vendored/generated dirs absent from the tree; `.gitignore`
  entries respected.
- **Extraction** — per-language outline correctness: kind, name, signature,
  docstring first-line, line number; fallback extractor still lists the
  unsupported-language file.
- **Ranking** — files emitted in reference-count order; ties break by path
  sort; identical output across repeated runs.
- **Focus** — `--focus PATH` expands the subtree and compresses the rest.
- **Token cap** — at descending `--max-tokens` budgets, output stays within
  budget and degrades in order: low-rank files dropped → signatures dropped →
  tree-only. Assert no mid-file truncation at any budget.
- **Index preference** — deferred with ADR-005 (DECISIONS.md): repoindex has
  not pinned its schema, so only the built-in counter exists to test. Add
  this area back when index-backed ranking lands.

## Running

`python -m pytest` from `tools/repomap/`.
