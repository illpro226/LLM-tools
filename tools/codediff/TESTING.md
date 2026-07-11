# codediff Testing

Fixture-based, per repo conventions (AGENTS.md). The PRD prescribes crafted
fixture diffs covering every section; each fixture is a scripted temp repo
with a before-commit and an after-state.

## Fixtures

Scripted repos, one per classification case:
- signature change (`old → new` in API);
- default-value change `3 → 5` (Behavior);
- added conditional and added/removed call (Behavior);
- rename with unchanged body (must classify as rename, not remove+add);
- deleted symbol carrying a deprecation marker (Removed);
- formatting-only and comment-only changes (Mechanical, one line);
- an auth-path change without test changes (sensitive-path and stale-tests
  flags, per docs/decisions/0002 — no graded severity), plus a variant with
  matching test edits and a `.codediff.toml` keyword override;
- Python, JS/TS, and Go variants of the core cases.

## Test areas

- **Inputs** — working tree vs HEAD, explicit ref, range, and `--staged` all
  produce the same model for equivalent content.
- **Classification** — each fixture lands in exactly its intended section
  with correct rendering (`old → new`, `3 → 5`, deprecation note,
  one-line Mechanical collapse); rename detection verified.
- **Risk** — the auth fixture raises the sensitive-path flag with its
  reason and `path:line`; the stale-tests flag clears when covering tests
  change; no ordinal grade appears anywhere in the output; `.codediff.toml`
  keywords respected; `tests`-table join used when a seeded index is
  present.
- **Outputs** — every finding has `path:line`; `--json` round-trips through a
  parser and mirrors the text model; `--max-tokens` collapses Mechanical
  first and never drops the Risk block.
- **Offline guarantee** — a network-blocking test double proves the default
  (and only) path opens no connection; there is no `--llm` flag (ADR-005).
- **Determinism** — identical output across runs per fixture.

## Running

`python -m pytest` from `tools/codediff/`. Requires `git` and the
`repoindex` package importable (`repoindex.extract`).
