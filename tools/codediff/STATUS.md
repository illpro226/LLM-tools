# codediff Status

Implemented (v0.6.1, 2026-10-09). Single-file CLI (`codediff.py`) with 70
tests in `tests/` against scripted temp repos; requires `git` and the
sibling `repoindex` package (`repoindex.extract`). Python and JS/TS
covered by fixtures; Go tracks repoindex's extractor but has no fixture
yet (see ROADMAP.md).

- `--max-tokens` defaults to 3000 rather than unbounded (ADR-007,
  docs/decisions/0005). `--json` is always full — a truncated payload is
  not parseable — and `--max-tokens 0` restores unbounded text output.
  Reduced rungs name at most 5 unanalyzed files (`… (+N more)`), so the
  floor stays bounded on a diff full of assets.
- Python signatures are read with string-aware comment stripping (a `#`
  in `color="#fff"` is not a comment), both sides drop a UTF-8 BOM before
  parsing, and files under `test/` and `__tests__/` count as tests.
- "formatting/comment-only" for JS/TS/Go comes from a literal-aware
  scanner: a `//` inside a string, template or regex is text. A change
  outside every extracted symbol reports `~ module-level code changed`.
- Sources split on newlines only, so a form feed or U+2028 cannot
  shift ast's line numbers off the lines they index.
- Paths come from `-z` git output, so spaces, quotes and tabs survive, and
  a rename counts only its own changed lines in the unanalyzed share.
- git discovery is bounded by `GIT_CEILING_DIRECTORIES`, defaulted to
  `$HOME` (ADR-008); `CODEDIFF_NO_CEILING=1` overrides.
- Markdown gets a structural pass rather than being skipped (ADR-009):
  heading deltas, body movement, and fenced-code changes, reported in a
  `Doc changes` section. Anything still unanalyzed is reported as a
  share of the change, in text and as `unanalyzed_share` in `--json`.
