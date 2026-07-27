# Guard hook: savings charged uncredited output against credited baselines (fixed 2026-07-26)

**FIXED 2026-07-26 (guard hook)** — `saved` now charges only credited
calls' output against the baseline, and a no-match raw run is n/a rather
than a 0-byte baseline. Found and fixed in one pass, so this entry goes
straight to `archive/` without ever appearing in the open list.

## Symptom

`savings_record.md` showed `sgrep` at ~-4,418 tokens, `gitbrief` at ~-1,667
and `structo` at ~-490 — three of the four measurable tools apparently
costing more context than the raw commands they replace. Only `xread`
scored positive.

## Cause

Two bugs in the guard hook's `_write_report` / `record_savings`
(`~/.claude/hooks/llm-tools-guard.py`), not anything the tools did.

1. **Mismatched aggregates.** `saved` was computed as
   `row["baseline_bytes"] - row["actual_bytes"]`, but `baseline_bytes`
   accumulates over *credited* calls only while `actual_bytes` accumulates
   over *every* call. Output from calls that never got a baseline was
   charged against savings with no offsetting raw equivalent. The penalty
   scaled with how often a tool's call shape was uncreditable, so the
   tools with the most n/a calls looked worst: 17 of 34 `sgrep` calls
   (`--files-only`/`--counts-only`, correctly excluded from baselining)
   contributed ~3,771 tokens of pure phantom loss.

2. **Zero-byte baselines credited.** `record_savings` only guarded
   `baseline_bytes is not None`, so a raw command that ran cleanly but
   matched nothing was recorded as a legitimate 0-token baseline and
   scored as total loss. The 2026-07-13 fix (see
   `guard-hook-sgrep-baseline-quote-mangling.md`) made *failing* raw runs
   return `None`, but a successful no-match run still returned 0. This
   alone accounted for `gitbrief`'s entire negative: 5 credited calls of
   which only 3 had a real baseline.

## Fix

- `saved` now uses a new per-tool `credited_actual_bytes` accumulator, so
  only the output of calls that got a baseline is charged against it.
- `record_savings` normalizes `baseline_bytes == 0` to `None`: a raw
  command that matched nothing is n/a, like any other underivable
  baseline.
- The report gained a `credited output` column so the all-calls and
  credited-only figures can't be conflated again by eye, and the footnote
  states which one is charged.
- Events now log `argv` (the suite call's argument tail, truncated to 500
  chars). The old schema recorded only `ts/tool/cwd/actual_bytes/
  baseline_bytes`, which made an anomalous row impossible to trace back to
  the call that produced it. `.savings/` is gitignored, so this stays
  machine-local.
- `.savings/aggregate.json` was rebuilt from `events.jsonl` under the
  corrected rules, replaying only the last N events per tool (N = the
  existing aggregate count) to preserve the deliberate 2026-07-13 drop of
  the poisoned `sgrep` rows, which remain in `events.jsonl`. Reconstructed
  `actual_bytes` matched the stored value exactly for all 8 tools.

Corrected totals: net ~117,096 (was ~97,231); `xread` ~112,258,
`structo` ~+5,111, `gitbrief` ~+361, `sgrep` ~-634.

## Takeaway

`sgrep` is still mildly net-negative, and that part is real, not a
measurement artifact. The credited calls show a clean crossover at roughly
150 tokens of raw `rg` output: below it `sgrep`'s per-match framing costs
more than the matches it frames (raw 8t → sgrep 36t; raw 24t → 343t),
above it `sgrep` compresses and the margin grows (raw 311t → 68t). Content
mode pays on broad searches; for searches expected to be narrow, lead with
`--files-only`/`--counts-only`. Those calls are excluded from baselining,
so the record stays silent about them either way.

One credited call remains unexplained: 343 tokens of `sgrep` output
against 24 tokens of raw `rg` in a repo where the two should have matched
the same lines. Pre-fix events carry no `argv`, so it can't be traced;
the new field exists for exactly this.
