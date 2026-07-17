# runlite Changelog

- 2026-07-17: v0.1.1 — Windows: resolve the wrapped command's argv[0]
  through `shutil.which` (PATHEXT-aware) before spawning, so `.cmd`/`.bat`
  shims like `npx`/`tsc` launch instead of exiting 127; detection and the
  not-found message keep the command as typed (fixes known-issue
  `runlite-npx-not-found-windows`). 27 tests.

- 2026-07-07: v0.1.0 — initial implementation: runner with exit-code
  passthrough, extractor registry (pytest, jest/vitest, go test, cargo, tsc,
  eslint, gcc/clang, generic fallback), `--max-tokens` budget rule,
  `--full-log` raw-log export; 25 fixture-based tests.
- 2026-07-06: Added initial documentation scaffold.
