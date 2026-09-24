# codediff Changelog

- 2026-09-24: v0.5.0 — fixes from a suite review, each pinned by a test
  that fails on v0.4.0.
  **A body edit was reported as a changed default.** Python signatures were
  cut at the first `#`, string or not, so `def paint(color="#fff"):` lost
  its closing paren, the "signature" ran on into the body, and changing
  `x = 1` to `x = 2` printed `~ paint()  default 1 → 2` — a false API
  claim. Comments are now stripped outside string literals only, and paren
  depth and the closing colon are read from a string-blanked skeleton.
  **A UTF-8 BOM hid every change in a file.** `ast.parse` rejects U+FEFF,
  so both sides parsed to no symbols and a real edit summarized as
  nothing. Worktree reads use `utf-8-sig` and blob reads drop the mark.
  **The floor was O(files).** Every unanalyzed file was named at every
  rung, so 300 changed assets kept the output over any budget; reduced
  rungs now name 5 and count the rest.
  **`test/` and `__tests__/` were source.** Only `tests/` marked a test
  directory, so jest (`__tests__`) and mocha/Maven (`test/`) suites were
  analyzed as behaviour changes and raised coverage flags against
  themselves.
  Also: the implicit `repoindex update` capture pins utf-8 (INVARIANTS: a
  non-ASCII path in its output could raise `UnicodeDecodeError` there);
  `diff.relative` is pinned off like gitbrief; a modified file is extracted
  once instead of twice. 5 new tests (54 total).
- 2026-09-11: v0.4.0 — new `Doc changes` section: markdown files get a
  structural pass (headings added/removed, bodies moved, fenced code
  changed) instead of falling out as "not analyzed" (ADR-009). Whatever
  remains unanalyzed is now stated as a share of the whole change —
  `4 of 6 files, 61% of changed lines not analyzed` — rather than as a
  trailing parenthetical, so the summary declares its own incompleteness.
  `--json` gains `unanalyzed_share`. Closes
  docs/known-issues/codediff-skips-markdown-so-doc-heavy-diffs-read-as-trivial.md.
  11 new tests (49 total).

- 2026-07-31: v0.3.1 — git repository discovery is bounded by
  `GIT_CEILING_DIRECTORIES`, defaulted to `$HOME` (ADR-008). Without it, a
  run outside any project walked up to a home directory that is itself a
  repo and scanned the whole tree — a multi-minute hang, not an error.
  Repos below `$HOME` are unaffected; `CODEDIFF_NO_CEILING=1` or your own
  `GIT_CEILING_DIRECTORIES` overrides. 4 new tests (38 total).
- 2026-07-31: v0.3.0 — `--max-tokens` now defaults to 3000 instead of unbounded
  (ADR-007, docs/decisions/0005-budgets-on-by-default.md); `--json` stays
  full because a truncated payload is not parseable, and `--max-tokens 0`
  restores the old behaviour for text. 2 new tests (34 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
- 2026-07-27: v0.2.0 — new `Tests` section: changed test files report one
  counted line (`+29 tests, +1 helper`) instead of enumerating every test
  function under API/Behavior. Test symbols therefore no longer inflate the
  behavior-delta or public-API risk flags — a better-tested change no longer
  reads as a riskier one. stdout pinned to UTF-8. 32 tests.
  Closes docs/known-issues/codediff-enumerates-every-new-test.md.
- 2026-07-11: v0.1.1 — the implicit `repoindex update` passes the
  `shutil.which()`-resolved path to `subprocess` instead of the bare
  command name (Windows `.cmd` PATH shims raise `FileNotFoundError` from
  a bare name; same fix as rq v0.1.2 and testmap v0.1.1). 28 tests.
- 2026-07-10: v0.1.0 — initial implementation. Symbol-level diff on
  `repoindex.extract` (both sides), sections API/Behavior/Removed/
  Mechanical, rename detection, flat explainable risk flags with
  `.codediff.toml` config and `tests`-table coverage joins, `--json`,
  `--max-tokens` level-wise degradation, 28 tests. Fixed worktree reads
  to resolve against the repo root so subdirectory invocation works.
- 2026-07-06: Added initial documentation scaffold.
