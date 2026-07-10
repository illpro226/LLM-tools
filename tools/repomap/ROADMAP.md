# repomap Roadmap

## M1 — Scaffold and tree view — done (v0.1.0)

- CLI entry point, fixture repo, test harness.
- Walker with skip list + `.gitignore` pruning; tree-only rendering.
- Deterministic ordering test.

## M2 — Symbol outlines — done (v0.1.0, stdlib not tree-sitter; ADR-004)

- Extraction for Python (ast) and JS/TS (one line per symbol with
  signature and docstring first-line).
- Generic regex fallback for unsupported languages.
- Go, Rust, C/C++ extractors.

## M3 — Ranking and focus — done except index preference (v0.1.0)

- Reference-count ranking; rank-ordered rendering.
- `--focus PATH` subtree expansion.
- Prefer `.repoindex/index.db` for ranking when present — deferred until
  repoindex pins its schema (ADR-005).

## M4 — Token budget — done (v0.1.0)

- bytes/4 estimator; `--max-tokens N` with staged degradation
  (drop files → drop signatures → tree-only), tested at descending budgets.
- As built, deep tree levels collapse first so the tree never starves the
  outlines.

## Later

- Index-backed ranking once repoindex lands (the `rank()` seam, ADR-005).
- Additional language extractors as needed; `--json` output if a consumer
  appears.
