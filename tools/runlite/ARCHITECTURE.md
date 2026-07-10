# runlite Architecture

Status: implemented (v0.1.0) in `runlite.py`, matching this design.

## Overview

`runlite` runs the wrapped command, captures the merged log, picks an extractor,
and renders a failure-focused report.

```
run(cmd) ──► {exit, wall_time, log}
detect(cmd, log) ──► extractor
extract(log) ──► problems[{message, file, line, context}]
render(problems, budget) ──► report (+ optional raw-log path)
```

## Components

- **Runner** — subprocess execution with stdout+stderr merged in arrival order,
  wall-clock timing, and exit-code capture. `runlite`'s own exit code mirrors the
  wrapped command's so it composes in scripts.
- **Extractor registry** — each extractor declares (a) a matcher (command name
  and/or log fingerprint) and (b) a parse function returning problems. Built-ins:
  pytest, jest/vitest, go test, cargo, tsc, eslint, gcc/clang. Detection tries the
  command name first, then log fingerprints, then falls back to generic.
- **Generic extractor** — keeps lines matching error/warning/fail patterns plus
  the last 20 lines of the log.
- **Problem model** — every problem carries a message and the nearest `file:line`
  reference found in or near its log region, plus a few context lines.
- **Renderer / budget** — header (exit code, wall time, problem counts), then
  problems. Over `--max-tokens N`: first failure in full, remaining failures as
  one line each. `--full-log PATH` writes the raw log to a scratch location and
  prints the path for follow-up with `xread`.

## Key decisions

- Language: Python; extractors are pure functions over text, so fixtures are
  canned logs and tests need no real toolchains.
- Extractors are heuristic by design — favoring "always show something useful"
  over perfect parsing; the raw log is the escape hatch.
- Adding an extractor = one module registering matcher + parser.

## Dependencies

Stdlib only.
