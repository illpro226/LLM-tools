# tokq Changelog

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
