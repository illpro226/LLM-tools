# 0007: Savings-log operations — no repeat-call memo, no compaction yet

Status: Accepted (2026-08-06)

Two questions raised by the 2026-08-06 review of `savings_record.md`, both
answered from `.savings/events.jsonl` rather than from intuition.

## Rejected: a memo for repeated identical calls

The review noticed 284 exact repeats (later 241 counting `cwd`, which is
the correct key — the same `xread app.py --symbol foo` in two projects is
not a repeat) and floated returning a cheap "same as before" for them.

Measured gap between a call and its repeat:

| gap | count |
|---|---:|
| < 1 min | 53 |
| 1–5 min | 34 |
| 5–60 min | 42 |
| 1–24 h | 62 |
| > 1 day | 50 |

The idea is wrong at both ends. Above an hour (112 of 241) the repeat is a
different task or a different session, and the file has almost certainly
changed — a memo there would serve stale content, which is worse than
spending the tokens. Under a minute (53) the dominant tool is `xread` (24),
and the overwhelmingly common shape is *read a symbol, edit it, read it
back*. That is precisely where a cached answer is actively wrong.

A content hash would make it safe, but safety is not the problem — value
is. The addressable set is at most the handful of sub-minute repeats where
nothing changed: roughly 2% of calls, a few thousand tokens a month,
against a permanent correctness hazard on the suite's most-used read path.

**Decision: not built.** Recorded here so it is not re-proposed from the
raw repeat count, which looks compelling until it is broken down.

## Deferred: compacting `events.jsonl`

The log is append-only and nothing trims it. At 205 bytes per event and
roughly 1,500 calls a month, it grows about 300 KB a month — 3.6 MB a
year. Disk is not the concern.

The concern is that `rebuild_aggregate()` re-reads and re-folds the *entire*
log on every suite call, by deliberate design: the aggregate is a pure
function of the event log, which is what let the v1 `sgrep` baseline bug be
retired without inventing replacement measurements. Measured cost of that
re-read:

| events | log size | read + parse |
|---:|---:|---:|
| 1,535 (today) | 0.3 MB | ~5 ms |
| 15,350 (~10 months) | 3.2 MB | ~46 ms |
| 76,750 (~4 years) | 15.8 MB | ~230 ms |

This is wall-clock on the hook, never model tokens. But INVARIANTS.md sets
a ~100 ms startup budget per tool, so at roughly ten months of use the
bookkeeping would cost as much as the tool it is measuring.

**Decision: no compaction now** — 5 ms does not justify machinery, and any
scheme risks the purity property that has already proved its worth once.

**Trigger to revisit: `events.jsonl` over ~4 MB, or the rebuild over 50 ms.**

**Shape when it comes:** seal events older than N days into
`events-archive.jsonl` plus a `sealed.json` of pre-folded per-tool totals;
`rebuild_aggregate()` reads sealed totals plus recent events only. Raw
history stays on disk, so a credit-rule change is still re-derivable with
one `--rebuild` over the archive. Do not delete events to make the file
small — that trades a recoverable cost for an unrecoverable one.
