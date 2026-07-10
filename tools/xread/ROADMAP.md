# xread Roadmap

## M1 — Scaffold and symbol mode

- CLI entry point, Python + TypeScript fixtures, test harness.
- `--symbol` with nested-name resolution and `path:start-end` headers.

## M2 — Line ranges and scope expansion

- `--lines A-B` raw ranges; `--scope` expansion to enclosing function/class.
- Region merger and elision markers.

## M3 — Query mode and multi-file

- `--query` block scoring and top-block selection.
- Multiple files per invocation with per-file grouping.

## M4 — Token budget

- `--max-tokens N` dropping lowest-value blocks first; no mid-block cuts;
  tests at descending budgets.

## Later

- More grammars (Go, Rust) as demand appears; `--context N` padding option.
