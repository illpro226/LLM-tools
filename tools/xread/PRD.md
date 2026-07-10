# xread PRD

## Problem statement

Whole-file reads are the single biggest token sink for coding agents: to see one function, an agent typically loads an entire 800-line file into context. `xread` returns just the relevant excerpt — a named symbol's body, a line range expanded to its enclosing scope, or the most relevant blocks for a keyword query — replacing most whole-file reads.

## Target users

- Coding agents that need a specific function, class, or region of a file.
- Humans who want a citable excerpt without opening an editor.

## Scope

### Modes

- `xread FILE --symbol NAME` — print the full body of a named function/class/method. Resolution is tree-sitter based and handles nested names like `ClassName.method`.
- `xread FILE --lines 120-140 --scope` — expand the given range to the enclosing function or class so the agent sees complete context.
- `xread FILE --query "text"` — score blocks by keyword match and print the top-scoring blocks.

### Output conventions

- Every excerpt starts with a one-line header in `path:startline-endline` form so results are citable.
- An elision marker (`… 240 lines elided …`) appears between non-adjacent excerpts.
- Plain text, deterministic, stable ordering.

### Shared behavior

- Multiple files may be read in one invocation.
- `--max-tokens N` caps total output; degrade by returning fewer/smaller blocks rather than cutting an excerpt mid-body.

## Non-goals

- Searching across a repo for where a symbol lives (use `sgrep` or `rq whouses`).
- Editing files or producing diffs.
- Rendering non-code data files (that is `structo`).

## Acceptance criteria

- `--symbol` returns the complete body of top-level and nested symbols in Python and TypeScript fixtures, including correct `path:line` headers.
- `--lines --scope` expands a mid-function range to the full enclosing function/class.
- `--query` returns the highest-scoring blocks first, deterministically.
- Elision markers appear between excerpts; adjacent excerpts are merged rather than duplicated.
- `--max-tokens` keeps output within budget without mid-excerpt truncation.
- Multi-file invocations group output per file with headers.
- Tests cover Python and TypeScript fixtures for all three modes.
