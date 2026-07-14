# Guard hook: sgrep savings baseline mangled quoted patterns (fixed 2026-07-13)

## Symptom

`savings_record.md` showed sgrep as a net token *loss* (-8,637 bytes /
~-2,334 tokens over 11 credited calls) with an implausible 105-byte total
baseline — ~10 bytes per raw `rg` run.

## Cause

Two bugs in the guard hook's `_sgrep_baseline` / `_run_raw_bytes`
(`~/.claude/hooks/llm-tools-guard.py`), not anything sgrep did:

1. The command tail was tokenized with naive `str.split()`, so
   `sgrep "def foo" src` produced a baseline run of `rg -n '"def' foo` —
   quote character kept, pattern split in half. The mangled `rg` matched
   almost nothing, making the baseline near zero while sgrep's real output
   counted in full.
2. `_run_raw_bytes` returned `len(stdout)` regardless of exit code, so the
   failed/no-match `rg` runs were recorded as legitimate 0-byte baselines
   instead of n/a, scoring every mangled comparison as pure loss.

Value-taking flags (`--max-tokens 500`, `-t py`, …) could also have their
values mistaken for the pattern positional.

## Fix

- Parse the tail with `shlex.split(posix=True)` so quoted patterns reach
  `rg` intact; a Windows path mangled by backslash escaping just fails the
  run and logs n/a.
- `_run_raw_bytes` returns `None` on non-zero exit — a baseline is only
  credited when the raw equivalent honestly ran and matched.
- Skip known sgrep value-flags when extracting positionals.
- The poisoned sgrep row was dropped from `.savings/aggregate.json`; sgrep
  stats restart clean from 2026-07-13. `.savings/events.jsonl` keeps the
  old raw events for reference.

## Takeaway

sgrep was never measured as wasteful — its savings verdict before
2026-07-13 is simply unknown. Watch the fresh numbers before drawing
conclusions about the tool itself.
