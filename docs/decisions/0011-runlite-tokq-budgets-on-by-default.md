# 0011 — runlite and tokq get a default budget too

Status: accepted
Date: 2026-10-09
Supersedes: the `runlite` and `tokq` part of 0005's exemption list

## Context

0005 turned budgets on by default but exempted `runlite`, `tokq`, `rq`,
`testmap` and `repoindex`, because "their output is already bounded by
construction (a failure report, a metering table, a query result)".

That premise does not hold for the first two. Measured on 2026-10-08
(known issue `runlite-default-output-unbounded-on-noisy-logs`):

- A command that printed 3,000 `warning:` lines and exited 1 made a
  **104,702-byte report from a 103,890-byte log**. The report was bigger
  than the log it was meant to replace. The generic extractor is
  O(log lines), and any extractor is O(failures) on a run with many
  failures. `runlite trace` is O(traces) on a service log.
- `tokq FILE...` prints one row per file, and `tokq lint` prints one row
  per finding. Both grow with the input.

All three had a bounded ladder already (`_degrade`, the trace summary
floor, and `_emit`'s elision line). None of those rungs ran unless
the caller passed `--max-tokens`, which 0005 measured on 1.4% of calls.

## Decision

`runlite`, `runlite trace` and `tokq` default to `--max-tokens 2000`, the
same as `xread`, `structo` and `gitbrief`. `--max-tokens 0` is still the
escape hatch, and runlite's `--full-log PATH` still writes every line.

The rest of 0005's list is unchanged: `repoindex` (a query result) and the
archived `rq`/`testmap`.

## Consequences

- An ordinary failure report (40–100 tokens per 0005's measurement), a
  passing run, or metering a handful of files is byte-identical with and
  without the default. Tests pin this.
- The 3,000-warning run now prints 8,220 bytes, about 2,000 tokens: the
  first problem in full, then one line per problem, cut and counted.
- INVARIANTS.md "the budget is on by default" no longer has an exception
  that contradicts its own premise for these two tools.

## Revisit if

A known-issue entry shows the 2000 default hiding the failure the caller
needed. runlite always keeps failure #1 in full, so that would mean a
first failure that alone exceeds the budget.

## Update 2026-10-09 (runlite v0.7.0)

The 8,220 bytes above were still 230 copies of one warning: a budget
caps noise, it does not remove it. runlite now collapses repeats
before the budget applies, and the same run prints 3 lines. The
default stays: it bounds what collapsing cannot, many *distinct*
problems.
