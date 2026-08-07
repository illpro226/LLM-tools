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
  pytest, jest/vitest, go test, cargo, tsc, eslint, gcc/clang, next build.
  Detection tries the command name first, then log fingerprints, then falls back
  to generic. Registry order matters for the fingerprint pass: `next build` sits
  ahead of jest/vitest because a green Next.js route legend trips jest's bullet
  fingerprint.
- **Generic extractor** — keeps lines matching error/warning/fail patterns plus
  the last 20 lines of the log.
- **Problem model** — every problem carries a message and the nearest `file:line`
  reference found in or near its log region, plus a few context lines.
- **Exit-code reconciliation** — on a zero exit the renderer drops `FAIL`-titled
  problems and names the extractor that produced them. Two signals that
  contradict each other must not both be printed; the exit code is the one that
  can't be pattern-matched wrong.
- **Suppressed-log size** — the header ends with `[log N B]`, the exact byte
  size of the captured log the report stands in for. It comes from the buffer
  runlite already holds, so it costs nothing to produce, and it is the only
  way to baseline runlite's savings without re-running the build.
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
