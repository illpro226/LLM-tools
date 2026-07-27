# codediff Changelog

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
