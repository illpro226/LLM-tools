# runlite's default output is unbounded and can exceed the log it replaces

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

A command that prints 3,000 `warning: thing N is deprecated` lines and
exits 1:

```
$ runlite -- python noisy.py
# runlite: exit 1 in 0.05s (generic) 3000 problems [log 103890 B]
...
# 6,023 lines, 104,702 bytes of report (~26k tokens)
```

The report is *larger* than the 103,890-byte raw log. Each errorish line
becomes a problem, plus a blank separator, plus the log tail. A failing
pytest run with hundreds of failures behaves the same way, because every
`FAIL` block is kept in full.

## Why

`runlite --max-tokens` defaults to 0 (unbounded). ADR-0005 exempts runlite
because its output is "already bounded by construction (a failure report)".
That holds for the language extractors on a typical run. It does not hold
for the generic extractor, which is O(log lines), or for any extractor on a
run with many failures. `runlite trace` defaults to 0 the same way, and its
output is O(traces) on a service log. `tokq lint` (O(findings)) and `tokq
FILE...` (O(files)) rely on the same exemption.

## What changed

Not fixed. Expected: a default budget for runlite (the `_degrade` ladder is
already built and bounded), or a supersession of ADR-0005's exemption that
records the measured counter-case. INVARIANTS.md "the budget is on by
default, and every rung is bounded" currently has an exception that does
not meet its own premise.
