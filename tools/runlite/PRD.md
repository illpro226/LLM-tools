# runlite PRD

## Problem statement

Agents re-run builds, tests, and linters constantly, and each run dumps thousands of lines of mostly-passing noise into context. What the agent needs is the exit status, the failures with a little context, and counts. `runlite` runs the command and returns only that — one of the highest-leverage token savings in the suite.

## Target users

- Coding agents running build/test/lint commands in an edit–run loop.
- Humans and CI scripts that want a failure-focused summary with the raw log preserved elsewhere.

## Scope

### Core behavior

- `runlite -- CMD ARGS...` executes the command, capturing stdout and stderr.
- Print a distilled report: exit code, wall time, then extracted problems.
- Ship built-in extractors (regex/heuristic based) for: pytest, jest/vitest, go test, cargo, tsc, eslint, gcc/clang.
- Generic fallback extractor: keep lines matching error/warning/fail patterns plus the last 20 lines of output.
- For each failure, include the failure message and the nearest `file:line` reference.

### Stack traces from elsewhere (added 2026-08-07, ADR-005)

- `runlite trace [FILE]` distills a stack trace runlite did not run: from a log file, CI output, a service, a paste. Reads stdin when FILE is absent or `-`.
- Languages: Python, Java/JVM, Node, Go, Rust. Output is the exception plus the frames that are this project's code; runs of library frames collapse to a counted line.
- Frames normalized to innermost-first, chained exceptions to propagated-first, so the output reads identically across languages.
- No inferred "probable cause": the suite is offline and deterministic, and a guessed cause carries no `path:line`.

### CLI surface

- `--max-tokens N` — when over budget, keep the first failure in full and summarize the remaining failures as one line each.
- `--full-log PATH` — also save the raw log to a file (in a scratch dir) and print its path, so an agent can drill in with `xread`.
- `trace --all-frames` — do not collapse runs of library frames.

### Output conventions

- Plain text, deterministic. Exit code of `runlite` reflects the wrapped command's outcome so it composes in scripts.

## Non-goals

- Choosing which tests to run (that is `testmap`).
- Retrying, parallelizing, or otherwise managing command execution.
- Streaming/interactive output; `runlite` is batch-oriented.

## Acceptance criteria

- Reports correct exit code and wall time for passing and failing commands.
- Each built-in extractor, fed a canned fixture log, extracts every failure with its message and nearest `file:line`.
- The generic fallback keeps error-like lines plus the last 20 lines for unknown tools.
- `--max-tokens` keeps the first failure in full and collapses the rest to one line each, within budget.
- `--full-log` writes the complete raw log and prints its path.
- Fixture-based tests cover each extractor, the fallback, and the over-budget path.
