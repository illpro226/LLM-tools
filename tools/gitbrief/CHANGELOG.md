# gitbrief Changelog

- 2026-09-24: v0.3.0 — fixes from a suite review, each pinned by a test
  that fails on v0.2.1.
  **Every count read `+0 -0` from a subdirectory.** Porcelain v2 status
  honours `status.relativePaths` and printed cwd-relative paths, while
  `diff --numstat` is always root-relative, so no stats lookup matched. The
  config is now pinned off: paths are root-relative everywhere (as `hunks`
  and `pr` already were) and the counts are right from any directory.
  Untracked line counts resolve against the toplevel, and `show` still
  recognises an untracked file named relative to the cwd.
  **User diff config reshaped parsed diffs.** With `diff.noprefix=true`,
  `hunks` stripped two characters off every path (`ols/tokq/README.md`);
  an external diff driver replaced the patch entirely. Parsed diffs now
  pin `--src-prefix=a/ --dst-prefix=b/ --no-ext-diff`, and
  `diff.relative` is pinned off.
  **The `hunks` floor was O(files).** One count line per file ignored the
  budget on a wide diff; the last rung now keeps the head of the list and
  totals the rest (`(… N more files, +P -M, for --max-tokens N)`).
  **`pr` was ~50 ms of process start per file side.** Blobs now come
  through one `git cat-file --batch` and ranges through `-U0` diffs 100
  paths at a time (anything the batch cannot key falls back to the
  per-file call): 6.7 s → 0.7 s on a 42-file branch, output byte-identical.
  Its Python scan also sees defs under module-level `if`/`try`/`with`, a
  BOM no longer turns a file's symbols into none, and the JS/TS scan
  counts code after a multi-line template's closing backtick.
  6 new tests (36 total).
- 2026-07-31: v0.2.1 — git repository discovery is bounded by
  `GIT_CEILING_DIRECTORIES`, defaulted to `$HOME` (ADR-007). Without it, a
  run outside any project walked up to a home directory that is itself a
  repo and scanned the whole tree — a multi-minute hang, not an error.
  Repos below `$HOME` are unaffected; `GITBRIEF_NO_CEILING=1` or your own
  `GIT_CEILING_DIRECTORIES` overrides. 4 new tests (30 total).
- 2026-07-31: v0.2.0 — `--max-tokens` now defaults to 2000 instead of unbounded
  (ADR-006, docs/decisions/0005-budgets-on-by-default.md); `--max-tokens 0`
  restores the old behaviour. `gitbrief hunks` on this repo's working diff
  drops from ~2,900 to ~310 tokens with no flag passed. 4 new tests
  (26 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
- 2026-07-27: v0.1.1 — stdout pinned to UTF-8 so echoed file content keeps
  its non-ASCII characters on Windows. Closes the gitbrief half of
  docs/known-issues/non-ascii-output-mangled-on-windows.md.
- 2026-07-08: v0.1.0 — initial implementation. Single-file stdlib CLI over
  git plumbing: default status+diffstat view with drift and last commits,
  `hunks` (U1), `show` (single-file full diff), `log` filters, `pr BASE`
  with stdlib changed-symbol lists (Python/JS-TS). `--max-tokens` staged
  degradation per mode; read-only enforced (`--no-optional-locks`,
  snapshot-tested). 20 temp-repo tests. ADR-005 (stdlib symbol extraction
  supersedes optional tree-sitter).
- 2026-07-06: Added initial documentation scaffold.
