# codediff Roadmap

Depends on `repoindex` shipping `repoindex.extract` as an importable library.

## M1 — Scaffold and symbol diff

- CLI with working-tree/ref/range/`--staged` inputs; fixture repos with
  crafted diffs.
- Before/after extraction via `repoindex.extract`; symbol alignment;
  added/removed/changed detection.

## M2 — Classification

- API section with `old → new` signatures; rename detection (not remove+add).
- Behavior detectors: default/literal changes, conditionals, call changes.
- Removed (with deprecation notes) and Mechanical (normalized-token
  comparison, one-line collapse).

## M3 — Risk

- Additive scorer with printed reasons; `.codediff.toml` keyword config;
  tests-changed signal from the shared `tests` table.

## M4 — Outputs

- `--json`; `--max-tokens N` (Mechanical collapses first); offline-by-default
  guarantee test. Optional `--llm` narrative over the compact delta.

## Later

- Commit-message draft mode; review-comment formatting.
