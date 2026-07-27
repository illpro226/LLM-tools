# structo: no way to aggregate across JSONL records

**RESOLVED 2026-07-26 (structo v0.3.0).** `--select f1,f2` shipped
(ADR-005): one TSV row per record — jsonl lines, a JSON array or YAML
sequence (top level or at `--path`), or CSV/TSV rows — with fields
addressed by the existing `--path` grammar. The issue's own suggestion,
taken over the `--group-by`/`--sum` alternative: aggregation stays with
`awk`/`sort`, which already do it and do it outside the agent's context.
The motivating query now runs in one line, with the 159-record log never
entering context:

```
structo .savings/events.jsonl --select tool,actual_bytes,baseline_bytes \
  | awk -F'\t' 'NR>1 {n[$1]++; a[$1]+=$2; b[$1]+=$3}
                END {for (t in n) printf "%-10s %4d %10d\n", t, n[t], b[t]-a[t]}'
```

The framing question the issue raised — whether this is structo's job at
all — was decided in favor of projection but against querying: no
filtering, sorting, or expressions either, so the projection stays a pure
per-record map and the streaming invariant holds (memory O(one record),
tracemalloc-enforced). PRD non-goals amended to match.

Original report follows.

**Date:** 2026-07-26
**Tool:** structo
**STATUS at filing:** Open

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
[`structo-jsonl-no-record-indexing.md`](structo-jsonl-no-record-indexing.md),
and it works — but it compounds with the guard hook denial in
[`../guard-hook-denies-ssh-remote-payloads.md`](../guard-hook-denies-ssh-remote-payloads.md): inline
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
