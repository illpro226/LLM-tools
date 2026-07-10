# gitbrief Testing

Per repo conventions (AGENTS.md) and the PRD: every test runs inside a
temporary git repo built by the suite — no committed fixture repos, no
dependence on the host's git state.

## Fixtures

- A test helper that scripts temp repos: initial commits, a feature branch, an
  upstream remote (local bare repo) with ahead/behind drift, staged + unstaged
  + untracked files with known +/- counts, and ≥5 commits.
- For `pr` symbol lists: files whose before/after versions add/remove known
  functions.

## Test areas

- **Default view** — branch name, ahead/behind counts, status+diffstat table
  rows and +/- counts exact across staged/unstaged/untracked, last 5 commit
  one-liners in order.
- **hunks** — headers with exactly 1 context line; file filtering respected.
- **show** — full diff for the named file, byte-comparable to `git diff`
  output for that file.
- **log** — `--grep`, `--author`, `-n` filters verified against scripted
  history.
- **pr** — merge-base diffstat and commit list vs a base branch; changed
  symbols (+added / ~modified / -removed) for Python and JS/TS files with
  known edits, untouched symbols absent; unanalyzed-language files named in
  a note. (Stdlib extraction per ADR-005 — always available, so there is no
  tree-sitter omission path to test.)
- **Token cap** — per-mode reduction rules (table→counts, context→drop,
  list shortening) at descending budgets.
- **Read-only guarantee** — repo state (HEAD, index, worktree hashes)
  identical before and after every mode.

## Running

`python -m pytest` from `tools/gitbrief/`. Requires `git` on PATH.
