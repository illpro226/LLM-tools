# tokq Changelog

- 2026-07-10: v0.1.1 — `dir` and `lint` output now uses `/` path separators
  on every platform (fixes known-issue
  `tokq-dir-backslash-paths-on-windows`; the Windows-only test failure in
  `test_dir_heaviest_first_with_percentages` is gone).
- 2026-07-07: v0.1.0 — initial implementation: meter (files/stdin), `dir`
  tree, `lint` rules (lockfile, minified, high-entropy, big file/data/dir,
  binary) with cheaper-tool suggestions and `--budget` gate; tiktoken/heuristic
  estimator with labeled output; 24 tests.
- 2026-07-06: Added initial documentation scaffold.
