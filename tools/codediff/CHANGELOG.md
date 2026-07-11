# codediff Changelog

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
