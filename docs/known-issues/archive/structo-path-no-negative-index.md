# structo: `--path` rejects negative JSONL record indices

**RESOLVED 2026-08-06 (structo v0.5.0):** `[-1]` selects the last record,
`[-2]` the one before, and sub-paths compose (`[-1].tool`). Implemented as
the ring buffer this issue proposed — `_nth_record` keeps a
`deque(maxlen=|N|)`, so memory stays O(schema + samples + |N|) and the
streaming invariant is intact (pinned by a test that asserts the buffer is
sized |N|, not the record count).

Two things beyond the ask, both cheap:

- The header resolves the index (`record -1 (1556)`). The reason you asked
  for `[-1]` is that you don't know the count, so the same call now tells
  you.
- A negative index *anywhere else* — inside a document, or in `--select` —
  is refused with the reason rather than silently reported as an absent
  path. Arrays are walked as an event stream with no length known until
  they close, so honoring `a.b[-1]` would mean buffering the array, which
  breaks the memory promise that is the whole point of streaming. Refusing
  loudly beats a confusing "--path not found".

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
