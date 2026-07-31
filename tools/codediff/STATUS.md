# codediff Status

Implemented (v0.3.0, 2026-07-31). Single-file CLI (`codediff.py`) with 34
tests in `tests/` against scripted temp repos; requires `git` and the
sibling `repoindex` package (`repoindex.extract`). Python and JS/TS
covered by fixtures; Go tracks repoindex's extractor but has no fixture
yet (see ROADMAP.md).

- `--max-tokens` defaults to 3000 rather than unbounded (ADR-007,
  docs/decisions/0005). `--json` is always full — a truncated payload is
  not parseable — and `--max-tokens 0` restores unbounded text output.
