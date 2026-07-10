# gitbrief PRD

## Problem statement

Agents habitually run `git diff` and `git log` and dump the raw output into context — hundreds of lines when a one-screen summary would do. `gitbrief` provides layered views of git state: a compact status+diffstat overview by default, hunk headers on request, and full hunks only for explicitly named files.

## Target users

- Coding agents checking repo state before/after edits and before commits.
- Humans who want a one-screen picture of where a working tree stands.

## Scope

### Default view

- Current branch and upstream drift (ahead/behind counts).
- A merged status+diffstat table covering staged, unstaged, and untracked files with +/- line counts per file.
- The last 5 commits as one-liners.

### Subcommands

- `gitbrief hunks [FILE...]` — diff hunk headers with 1 context line each.
- `gitbrief show FILE` — the full diff for one file.
- `gitbrief log --grep/--author/-n` — condensed history.
- `gitbrief pr BASE` — whole-branch summary vs a base: diffstat, commit list, and a changed-symbol list (using tree-sitter when available).

### Shared behavior

- All modes respect `--max-tokens N`.
- Implementation uses pure `git` plumbing subprocess calls; no libgit dependency.
- Plain-text, deterministic output.

## Non-goals

- Semantic interpretation of changes (that is `codediff`).
- Mutating repo state — no staging, committing, or branching.
- Replacing `git` for humans who want full diffs; `gitbrief show` is the escape hatch.

## Acceptance criteria

- In a temp repo created by the test suite, the default view shows branch, ahead/behind, a correct status+diffstat table across staged/unstaged/untracked files, and 5 commit one-liners.
- `hunks` emits hunk headers with exactly 1 context line; `show` emits the full per-file diff.
- `log` filters by grep/author/count correctly.
- `pr BASE` reports diffstat, commit list, and changed symbols for a branch with known edits.
- Every mode stays within `--max-tokens` budgets in tests.
- No libgit2/dulwich-style dependency appears in the dependency list.
