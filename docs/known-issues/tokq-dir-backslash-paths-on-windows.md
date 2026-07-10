# tokq: `dir` output uses backslash paths on Windows

**RESOLVED 2026-07-10 (tokq v0.1.1):** `_walk` now normalizes relative
paths to `/`, and `dir`'s root header plus `lint`'s reported paths are
normalized at the render sites. The Windows test failure is gone.

- **What breaks:** `tokq.py dir PATH` prints nested entries with the native
  separator (`sub\b.txt`) instead of `/`. One test fails on Windows:
  `tests/test_tokq.py::test_dir_heaviest_first_with_percentages` expects
  `sub/b.txt`.
- **When:** any `tokq dir` run on Windows (found 2026-07-07 running the
  suite there; tokq was developed in a Linux container).
- **Expected:** suite convention is deterministic output across runs *and*
  platforms — path-shaped output should be normalized to `/` (as `repomap`
  and the test expectation already assume).
- **Workaround:** none needed for consumption; for CI on Windows the test
  fails until fixed.
- **Fix shape:** normalize relative paths with `.replace(os.sep, "/")` at
  the render site in `tools/tokq/tokq.py` (dir mode), matching the test.
