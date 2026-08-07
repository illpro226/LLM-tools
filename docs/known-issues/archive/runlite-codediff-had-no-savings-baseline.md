# runlite and codediff logged hundreds of calls with no savings baseline

**FIXED 2026-08-06 (runlite v0.3.0 + guard hook event schema v3).**
`codediff` is now baselined against the raw `git diff` for the same
revision range, by the method `gitbrief` already used. `runlite` reports
its own captured-log size in its header (`[log N B]`), giving the hook an
exact baseline without re-running the build.

**Date:** 2026-08-06
**Tool:** runlite, codediff, LLM-tools guard hook (savings recorder)

## What happened

`savings_record.md` credited nothing to `runlite` (180 calls, ~22k tokens
of output) or `codediff` (61 calls, ~56k tokens — the most expensive
output per call in the suite at ~915 tokens). Both showed `n/a` in every
savings column, so the record could not answer whether either tool was
worth its own output. `codediff` in particular was the suite's largest
unexamined expense.

The hook's stated reason was that neither had a derivable raw equivalent.
That was true for `runlite` and wrong for `codediff`.

## Fix

**`codediff`** — the baseline is `git diff` for the same revision range,
by exactly the method `gitbrief` already used. codediff's entire claim is
that reading what a change *means* beats reading the hunks, so the hunks
are the honest comparison. `--staged`, a bare `REF`, and `A..B` all map
through; value-taking flags (`--max-tokens N`) are skipped so their
argument is not read as a revision. `--json` is credited too — it is the
narrator payload, not a machine-only export, and answers the same question
at the same altitude.

First credited call measured 346 tokens of codediff output against 14,885
tokens of raw diff.

**`runlite`** — re-running a build to size its log would be slow,
side-effecting, and not even deterministic. Instead runlite reports the
figure itself: its header now ends with `[log N B]`, taken from the buffer
it already holds, so the baseline is *exact* rather than estimated — the
only one in the record that is. The line earns its ~12 bytes twice over:
it also tells the reader how much log was suppressed, which distinguishes
a four-line summary of 400 KB from a four-line summary of 900 B.

Event schema bumped to v3. Pre-v3 rows for both tools stay uncredited
rather than being back-filled with invented measurements — the builds they
summarized are gone.
