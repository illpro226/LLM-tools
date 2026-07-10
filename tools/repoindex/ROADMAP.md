# repoindex Roadmap

The foundation for `callgraph`, `rq`, `testmap`, and `codediff` — sequenced
ahead of them (build-order step 4 in START.md).

## M1 — Schema and Python extraction

- SQLite schema with indexes; fixture repo.
- `repoindex.extract` interface; Python extractor covering symbols, imports,
  inherits, and raw refs.
- `build` command; per-table row verification tests.

## M2 — Resolution and remaining languages

- Import + scope-aware reference resolution; `confidence=heuristic` for
  unresolved/dynamic edges.
- JS/TS and Go extractors through the same interface.
- Convention/import-derived `tests` rows with `source` tags.

## M3 — Incremental updates

- `update` with mtime/hash change detection, single-transaction rewrite;
  test proving an untouched file is not re-parsed.
- `status` (freshness, per-language counts); `.gitignore` handling.

## M4 — Escape hatch and library polish

- `sql` read-only query command with column alignment and write rejection.
- Public library surface for `codediff` (parse a standalone file version);
  interface docs for adding a language.

## Later

- Rust/C++ extractors; symbol signature storage if `rq publicapi` needs it.
