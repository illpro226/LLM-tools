# structo: `--path` rejects negative JSONL record indices

**Date:** 2026-08-06
**Tool:** structo (v0.2.0+)

## What I tried

Checking the most recently appended event in the savings log, to confirm a
new guard-hook baseline had been recorded:

```
$ structo .savings/events.jsonl --path "[-1]"
structo: bad --path '[-1]' (expected like a.b[0].c)
$ structo .savings/events.jsonl --path "[-1].tool"
structo: bad --path '[-1].tool' (expected like a.b[0].c)
```

## When it happens

Any append-only JSONL file where the interesting record is the newest one
and the record count is unknown. That is the normal shape for logs —
`events.jsonl`, session transcripts, ndjson exports.

`[N]` from the fix in
[`archive/structo-jsonl-no-record-indexing.md`](archive/structo-jsonl-no-record-indexing.md)
only helps if you already know N, which for a growing file means running
structo once to learn the count and again to fetch the record.

## Expected

`[-1]` selects the last record, `[-2]` the one before it, matching Python
slice conventions the syntax already resembles. Paths inside the record
should compose as usual (`[-1].tool`).

Cost is bounded: structo streams, so a negative index needs a ring buffer
of the last |N| records, not the whole file. Memory stays O(schema +
samples + |N|), which keeps the streaming invariant intact.

## Workaround

`structo FILE --select f1,f2 | tail -3`, which is what this session used.
It works but returns a TSV row rather than the record's structure, so it
answers "what value" and not "what shape" — and it re-renders every record
in the file to show the last one.
