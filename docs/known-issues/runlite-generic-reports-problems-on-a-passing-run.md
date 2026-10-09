# runlite's generic extractor reports "problems" on a passing run

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

A command that exits 0 and prints a clean summary:

```
$ runlite -- python ok.py
# runlite: exit 0 in 0.05s (generic) 2 problems [log 71 B]

compiled 12 files, 0 errors, 0 warnings

error handling module loaded

log tail (last 2 lines)
  ...
```

"2 problems" under `exit 0` is the contradiction the exit-0 filter was
written to prevent. It is read and reported as "the build has problems".

## Why

`render` drops failure-shaped findings on exit 0, but it recognizes them
only by a `FAIL`/`FAILED` title. The generic extractor titles a finding with
the raw log line, which matches anything containing `error`, `warning`,
`fail` and so on, including `0 errors` and `error handling`.

## What changed

Not fixed. Expected: on exit 0, the generic extractor reports no problems,
only an optional `warnings: N` count. The language extractors already know
their own warning shapes. At minimum, ignore lines where the keyword is
preceded by `0 `/`no `.
