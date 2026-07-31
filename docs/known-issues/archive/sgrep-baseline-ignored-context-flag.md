# sgrep's savings baseline ignored `-C`, manufacturing a fake net loss

**FIXED 2026-07-31 (guard hook)** — the sgrep baseline now mirrors
`-C`/`-i`/`-F`/`-w`/`-t`/`-g` and every path, event fairness is decided at
read time via a schema version, and `aggregate.json` is a pure fold over
`events.jsonl`. sgrep reads +7,874 tokens instead of -14,795.


Filed 2026-07-31. **Fixed the same day** — kept as the record of how the
meter misread a tool.

## Symptom

`savings_record.md` showed `sgrep` as the only net-negative tool in the
suite: **−14,795 tokens** across 132 credited calls, roughly −112 per call,
while every other measured tool showed large positive savings. Read
literally, the most-used tool in the suite (316 calls, ~48% of all traffic)
was costing more than the raw `rg` it replaced.

## Cause

The guard hook's `_sgrep_baseline` built the comparison command as:

```python
cmd = [rg, "-n", positional[0]] + positional[1:2]
```

Every flag was stripped before the baseline ran — including `-C`. So a call
like `sgrep "EntityHeader" src -C 4`, which correctly printed four lines of
context per match (11,581 bytes), was scored against `rg -n "EntityHeader"
src`, which prints one line per match (1,295 bytes). The baseline answered a
different, much cheaper question than the call it was compared against.

Splitting the credited calls on that axis:

| | calls | actual | baseline | net |
|---|---:|---:|---:|---:|
| used `-C` | 33 | 81,283 B | 7,355 B | **−19,980 tok** |
| no `-C` | 101 | 63,048 B | 77,860 B | **+4,003 tok** |

The entire deficit lived in 33 calls and was an artifact in all 33.

Two smaller biases pushed the same way: the baseline kept only
`positional[1:2]` (one path, though calls often pass several), and the
`rest` string still contained the shell tail (`2>&1 | head -160`), whose
tokens were only harmless because the single-path slice discarded them.

## Fix

- The baseline now mirrors every flag that changes which lines `rg` prints
  (`-C`, `-i`, `-F`, `-w`, `-t`, `-g`) and passes all paths, so both sides
  answer the same question.
- A shared `_shell_tokens()` truncates the argument string at the first
  unquoted shell operator. It is quote-aware on purpose: a bare split on
  `|` would cut a quoted alternation like `'queryRaw|executeRaw'` in half
  and silently measure a different search.
- Events carry a schema version. Fairness is decided at *read* time
  (`_event_credited`), so v1 `-C` rows are excluded from the totals rather
  than restated — the working trees they ran in are gone, and inventing
  replacement measurements would be worse than admitting the gap.
- `aggregate.json` is now a pure fold over `events.jsonl` (rebuild with
  `python llm-tools-guard.py --rebuild`). The old incremental counter had
  already drifted — it recorded 321 sgrep calls against 331 logged events —
  and could not be corrected when a baseline rule changed.

After the fix `sgrep` reads **+7,874 tokens**, and the suite total rose
from ~905k to ~1.17M.

## Lesson

A measurement that flatters the thing being measured gets scrutinized; one
that maligns it gets believed. This nearly cost a good tool its place in
the suite on the strength of a number that was never comparing like with
like. Any baseline in this meter must run the *same question* as the call
it scores, and the fairness rule belongs at read time so it can be revised
without rewriting history.
