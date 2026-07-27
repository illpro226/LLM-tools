# structo

Prints the schema and shape of a data file — keys, types, optionality,
array lengths, column stats, log templates, and a couple of samples —
instead of the content. A 2 MB JSON dump becomes twenty lines.

```
./structo.py FILE                summarize (format auto-detected:
                                 json/jsonl/yaml/csv/tsv/xml/log)
./structo.py FILE --path a.b[0].c    zoom into a JSON/YAML subtree
                                 (a leading [N] picks JSONL record N)
./structo.py FILE --raw --path ...   print the exact value at --path
                                 (strings verbatim, else JSON)
./structo.py FILE --select a,b.c     one TSV row per record, for piping
./structo.py FILE --sample N     array elements aggregated (default 10)
./structo.py FILE --max-tokens N cap output; samples go first, top-level
                                 structure never does
```

Everything streams — memory is O(schema + samples), never O(file), which
is test-enforced. Figures affected by sampling carry a `~` marker; clean
figures are exact. Output is plain text and deterministic (sampling is
first-N, no RNG).

`--raw` turns structo into an extractor: it prints the value itself, not
its schema — strings verbatim (so a field pipes cleanly into a file),
everything else as JSON. It still streams (only the returned value is
materialized), and with `--max-tokens` it refuses rather than truncates —
an exact value can't be summarized (ADR-004).

`--select` is the other way out of schema-only output: it projects chosen
fields from *every* record as TSV, so a log can be measured without being
read. Records are jsonl lines, a JSON array or YAML sequence (top level or
at `--path`), or CSV/TSV rows; fields use the `--path` grammar.

```
structo .savings/events.jsonl --select tool,actual_bytes,baseline_bytes \
  | awk -F'\t' 'NR>1 {n[$1]++; a[$1]+=$2; b[$1]+=$3}
                END {for (t in n) printf "%-10s %4d %10d\n", t, n[t], b[t]-a[t]}'
```

There is no `--group-by`/`--sum`: `awk` and `sort` already aggregate, and
they do it outside the agent's context, which is the entire point
(ADR-005). Missing fields are empty cells, JSON `null` renders `null`,
containers render as compact JSON, and tabs/newlines in values become
spaces so one record is always one row. Like `--raw`, `--select` with
`--max-tokens` refuses rather than dropping records.

Stdlib-only single file except YAML, which uses PyYAML's event API when
installed. `python -m pytest` from this directory runs the tests
(`-m "not slow"` skips the large-file memory test). See
[`DECISIONS.md`](DECISIONS.md) for the ADRs.
