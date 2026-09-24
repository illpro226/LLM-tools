# gitbrief Status

Implemented (v0.3.0) and passing tests.

- `gitbrief.py` — single-file, stdlib-only CLI over subprocess `git`
  plumbing (`status --porcelain=v2 --branch`, `diff --numstat`,
  `log --format`, `merge-base`; always `--no-optional-locks`, colors off,
  rename detection off so a rename reads as delete + add).
- Modes: default view (branch + ahead/behind, merged status+diffstat table
  across staged/unstaged/untracked with per-file +/- counts, last 5 commit
  one-liners), `hunks [FILE...]` (1-context-line diff vs HEAD), `show FILE`
  (full single-file diff — the deliberate escape hatch, byte-identical to
  `git diff HEAD -- FILE`), `log --grep/--author/-n`, `pr BASE`
  (merge-base diffstat, commit list, changed top-level symbols).
- `pr` changed symbols come from stdlib extraction of the before/after
  blobs for Python (`ast`) and JS/TS (brace scanner), classified
  +added / ~modified / -removed by diff-range intersection — ADR-005,
  superseding the optional-tree-sitter plan. Other languages are listed
  in a "not analyzed" note.
- Every mode takes `--max-tokens N` (bytes/4) and degrades by whole
  levels: table→counts, hunk context→headers→counts, list shortening. The
  `hunks` floor keeps the head of the per-file list and totals the rest,
  so even a thousands-of-files diff fits the budget.
- Paths are repo-root-relative in every view, from any subdirectory
  (`status.relativePaths` and `diff.relative` are pinned off). Parsed
  diffs pin `a/`/`b/` prefixes and `--no-ext-diff`, so user diff config
  (`noprefix`, `mnemonicPrefix`, an external driver) cannot reshape them.
- `pr` reads blobs through one `git cat-file --batch` and ranges through
  chunked `-U0` diffs (~10x faster than a `git show` + `git diff` per
  file); Python symbols include defs under module-level `if`/`try`/`with`,
  and a BOM no longer hides a file's symbols.
- `--max-tokens` defaults to 2000 rather than unbounded (docs/decisions/0005);
  `--max-tokens 0` restores unbounded output.
- git discovery is bounded by `GIT_CEILING_DIRECTORIES`, defaulted to
  `$HOME` (ADR-007); `GITBRIEF_NO_CEILING=1` overrides.
- Tests: `tests/test_gitbrief.py` (35 tests) against temp repos scripted
  by the suite (upstream drift via a local bare remote, staged + unstaged
  + untracked with exact counts, feature branch with known symbol edits);
  host git config is neutralized. A repo-state snapshot asserts every
  mode is read-only. Requires `git` on PATH.

Not done / later: untracked files have no `show` view (use xread);
rename detection intentionally off; symbol analysis limited to Python
and JS/TS top-level declarations.
