# Budget ladders were opt-in, and two of them didn't terminate

**RESOLVED 2026-07-31 (sgrep v0.2.0, xread v0.3.0, structo v0.4.0,
gitbrief v0.2.0, repomap v0.3.0, codediff v0.3.0)** — every growable
digest now caps itself by default (docs/decisions/0005), structo's ladder
gained sibling-key rungs so it terminates, xread no longer drops its sole
region, and sgrep announces reduced context.


Filed 2026-07-31. **Fixed the same day** (docs/decisions/0005).

## Symptom

Every tool documented a `--max-tokens` degradation ladder. Every ladder was
implemented and tested. Almost none of them ever ran.

Across the first 661 logged suite calls (`.savings/events.jsonl`), **9
passed `--max-tokens` — 1.4%**. Meanwhile 19 calls emitted more than 2,000
tokens each, 74,622 tokens in total: about 8% of everything the suite
printed, produced by 3% of its calls. The p99 call for `xread` was 7,817
tokens; for `sgrep`, 2,553; the single largest was 8,431.

Every `--max-tokens` in the suite defaulted to `0`/`None`, meaning
unbounded.

## Why this is a defect and not a preference

The suite exists to keep raw bulk out of a context window. A tool that
emits raw bulk unless asked twice is not doing that job — it is offering
to. And the flag only helps the caller who already suspected the output
would be large, which is exactly the caller who did not need help. The
calls that flood a context window are the ones nobody expected to:
`gitbrief hunks` on a diff that grew, `repomap` on a bigger repo than last
time, `sgrep -C 12` on a pattern that turned out to be common.

## Two ladders were also broken

Turning the defaults on surfaced bugs that an opt-in cap had hidden:

- **`structo` ignored the budget entirely for wide records.** The ladder's
  deepest rung was "top-level keys only" — still one line per key, so still
  O(input). A 4,000-key object emitted ~12,800 tokens against
  `--max-tokens 200`. Not loose: ignored. `render_schema` gained a
  `key_cap` and the ladder now continues through 100/40/15/5 siblings with
  a `… (+N more keys)` note; the same object renders in ~150 tokens.
- **`xread` dropped its sole region whole** when no blank line was
  available to trim at, returning `(dropped for --max-tokens: …)` and
  nothing else — the one degradation that answers no part of the question.
  It now halves the region toward its head until it fits.

A rung that is still proportional to the input is not a rung.

## Also fixed: silent degradation

`sgrep` reduces context first (its ADR-003), and said nothing about it.
With the cap opt-in that was tolerable; with it on by default it is
actively misleading, because dropped context reads as *absent* context —
the caller concludes the surrounding lines don't exist rather than that
they were trimmed, and never thinks to raise the cap. It now prints
`(context reduced 3 -> 1 for --max-tokens 1500)`.

## Result

Measured on this repo, with no flag passed: `repomap .` fell from ~15,000
to ~2,900 tokens, `gitbrief hunks` from ~2,900 to ~310. Defaults are
calibrated near the 95th percentile of measured per-call output, and each
tool's suite asserts that a small input produces byte-identical output with
and without the default.

## Lesson

Shipping the mechanism is not shipping the behaviour. Both these ladders
had tests, docs and an ADR; what neither had was a default that made them
run. When a safeguard is opt-in, measure how often it is actually opted
into before believing it works.
