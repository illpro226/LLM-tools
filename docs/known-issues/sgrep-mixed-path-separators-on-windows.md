# sgrep: mixed path separators on Windows depending on how the path was given

**Date:** 2026-08-06
**Tool:** sgrep (v0.4.0)

## What happens

Search a directory and the results come back with backslashes; search the
same file by naming it explicitly and they come back with forward slashes:

```
$ sgrep "def render" tools/sgrep
== tools/sgrep\sgrep.py (1 match) ==
tools/sgrep\sgrep.py:211: def render(ranked, files, ...

$ sgrep "def render" tools/sgrep/sgrep.py
== tools/sgrep/sgrep.py (1 match) ==
tools/sgrep/sgrep.py:211: def render(ranked, files, ...
```

The separator is whatever `rg` produced: the prefix comes from the
argument, the rest from directory traversal. Passing several paths puts
both forms in one output.

## When it happens

Windows only, on any directory-scoped search — which is the default shape
of the call. Same class as the resolved
[`archive/tokq-dir-backslash-paths-on-windows.md`](archive/tokq-dir-backslash-paths-on-windows.md),
in a different tool.

## Why it matters beyond cosmetics

The `path:line` reference exists so a finding can be followed up with
`xread` (INVARIANTS.md). A mixed-separator path is still valid input to
`xread`, so nothing breaks — but it is unstable output for a suite that
promises deterministic, stable ordering, it makes two references to the
same file compare unequal as strings, and it defeats grouping when a caller
pipes results into something that keys on path.

## Expected

Normalize to forward slashes in output regardless of how the path was
supplied, as `tokq dir` now does. Paths are display-and-reference values
here, never reopened by sgrep itself, so normalizing costs nothing.

## Workaround

None needed for correctness; both forms work with `xread`. Be aware when
diffing or deduplicating sgrep output across runs.
