# tokq Changelog

- 2026-09-24: v0.1.2 — fixes from a suite review, each pinned by a test
  that fails on v0.1.1. **`--max-tokens` cut the summary.** Output was
  truncated from the end, which is where the total, the finding count and
  the `BUDGET EXCEEDED` lines live: a capped `tokq lint --budget` exited 1
  with no line saying which path was over. Rows are now elided and the
  summary always prints. **`lint` stopped at the first missing path**,
  discarding every finding made before it; it now reports the path on
  stderr, lints the rest, and exits 2. **An unreadable file ended a walk
  in a traceback** (`getsize` in `_walk` was unguarded); it is skipped.
  STATUS had also drifted to v0.1.0 and 24 tests. 5 new tests (30 total).
- 2026-07-31: stderr pinned to UTF-8 at entry alongside stdout. Error messages
  carry the same non-ASCII punctuation as normal output (em dashes,
  ellipses, arrows); on a cp1252 console they reached the caller as
  invalid UTF-8 bytes. stdout was already pinned, but always after the
  error path had already printed.
- 2026-07-27: v0.1.1 — stdout pinned to UTF-8 so non-ASCII paths and lint
  excerpts survive a cp1252 console.
- 2026-07-10: v0.1.1 — `dir` and `lint` output now uses `/` path separators
  on every platform (fixes known-issue
  `tokq-dir-backslash-paths-on-windows`; the Windows-only test failure in
  `test_dir_heaviest_first_with_percentages` is gone).
- 2026-07-07: v0.1.0 — initial implementation: meter (files/stdin), `dir`
  tree, `lint` rules (lockfile, minified, high-entropy, big file/data/dir,
  binary) with cheaper-tool suggestions and `--budget` gate; tiktoken/heuristic
  estimator with labeled output; 24 tests.
- 2026-07-06: Added initial documentation scaffold.
