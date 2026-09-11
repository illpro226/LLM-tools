# codediff Status

Implemented (v0.4.0, 2026-09-11). Single-file CLI (`codediff.py`) with 49
tests in `tests/` against scripted temp repos; requires `git` and the
sibling `repoindex` package (`repoindex.extract`). Python and JS/TS
covered by fixtures; Go tracks repoindex's extractor but has no fixture
yet (see ROADMAP.md).

- `--max-tokens` defaults to 3000 rather than unbounded (ADR-007,
  docs/decisions/0005). `--json` is always full — a truncated payload is
  not parseable — and `--max-tokens 0` restores unbounded text output.
- git discovery is bounded by `GIT_CEILING_DIRECTORIES`, defaulted to
  `$HOME` (ADR-008); `CODEDIFF_NO_CEILING=1` overrides.
- Markdown gets a structural pass rather than being skipped (ADR-009):
  heading deltas, body movement, and fenced-code changes, reported in a
  `Doc changes` section. Anything still unanalyzed is reported as a
  share of the change, in text and as `unanalyzed_share` in `--json`.
