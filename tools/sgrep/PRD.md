# sgrep PRD

## Problem statement

A raw grep over a real codebase returns thousands of lines, most of them near-duplicates or hits in tests/generated files. Agents dump that firehose straight into context. `sgrep` wraps ripgrep and condenses results into a ranked, deduplicated digest — a 3,000-line grep dump becomes a ~60-line summary that preserves the signal.

## Target users

- Coding agents searching for symbols, strings, or patterns during a task.
- Humans who want ranked search results instead of raw match streams.

## Scope

### Core behavior

- Shell out to `rg --json` and post-process the results; never reimplement the matcher.
- Group matches by file with a per-file match count.
- When a file has more than 5 matches, show the 3 most distinct ones (deduplicated by normalized line content) plus a `(+12 more similar)` note.
- Rank files by match density and path heuristics — prefer `src` over tests over generated files; heuristics configurable.

### CLI surface

- `sgrep PATTERN [PATH...]` — condensed search.
- `--files-only` — matching file list only (cheapest mode).
- `--counts-only` — file list with match counts.
- `--max-tokens N` — global cap; reduce in order: context lines, then matches per file, then files shown.

### Output conventions

- `path:line: content` lines under a per-file header. Plain text, deterministic ordering.
- If ripgrep is not installed, exit with a short, clear error explaining how to install it.

## Non-goals

- Semantic or index-backed search (that is `rq` over `repoindex`).
- Replacing ripgrep's own flag surface; only the flags that matter for condensing are exposed.
- Editing or refactoring based on matches.

## Acceptance criteria

- Against a fixture tree, matches are grouped by file with counts, and files rank by density and path preference (src before tests before generated).
- A file with >5 matches shows exactly 3 distinct representatives plus a correct `(+N more similar)` note.
- Near-identical lines are deduplicated by normalized content.
- `--max-tokens` reduces context lines first, then matches per file, then files, verified by tests at descending budgets.
- `--files-only` and `--counts-only` emit their cheaper formats.
- The no-ripgrep case produces a clear error and nonzero exit, covered by a test.
