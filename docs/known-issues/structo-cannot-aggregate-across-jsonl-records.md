# structo: no way to aggregate across JSONL records

**Date:** 2026-07-26
**Tool:** structo
**Status:** Open

## What I tried

Analyzing the guard hook's own telemetry (`.savings/events.jsonl`, 134
records) to answer "which sgrep call shapes run net-negative?" — a
group-by-tool sum over two numeric fields, plus a sort to find outliers.

`structo` gives the shape and can address one record:

```
structo .savings/events.jsonl              # schema, 134 records
structo .savings/aggregate.json --path sgrep --raw
```

Neither answers the question. There is no way to sum `actual_bytes`
grouped by `tool`, or to rank records by a computed delta.

## Expected

Some aggregation over records, e.g. `--group-by tool --sum actual_bytes`,
or a `--select` that emits chosen fields as TSV so the caller can pipe to
`awk`/`sort` without loading the file into context.

## Impact / workaround

Wrote four throwaway Python scripts (`an.py`, `an2.py`, `an3.py`,
`an4.py`) in the scratchpad and ran them. That is the documented fallback
from the resolved
[`archive/structo-jsonl-no-record-indexing.md`](archive/structo-jsonl-no-record-indexing.md),
and it works — but it compounds with the guard hook denial below: inline
`python -c` JSON parsing is (correctly) denied, so every iteration of an
exploratory aggregation costs a Write plus a Bash call rather than one
line. Five iterations to characterize one tool's cost curve.

Worth weighing against scope: structo's job is schema/shape, and a query
language is a different tool. The honest framing may be that
"analyze a JSONL log" is not structo's job at all and the suite simply
has no tool for it — in which case this issue is evidence for that gap,
not for growing structo. Note the data here is the suite's *own*
telemetry, so the gap is self-inflicted and recurring: the same analysis
will be wanted every time the savings record looks wrong.
