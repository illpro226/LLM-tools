# codediff Roadmap

M1–M4 shipped in v0.1.0 (2026-07-10), as amended by `docs/decisions/0002`
and DECISIONS.md ADR-004/ADR-005 — see the per-milestone notes below.
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

- Flat, individually explainable flags with printed reasons (no scorer or
  grade — docs/decisions/0002); `.codediff.toml` keyword config;
  tests-changed signal from the shared `tests` table.

## M4 — Outputs

- `--json`; `--max-tokens N` (Mechanical collapses first); offline-by-default
  guarantee test. No `--llm` — `--json` is the narrator payload (ADR-005).

## Later

- Commit-message draft mode; review-comment formatting.
- A Go fixture for the core classification cases (the extractor already
  tracks repoindex's Go support; only test coverage is missing).
