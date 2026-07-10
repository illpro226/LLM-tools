# structo

Prints the schema and shape of a data file — keys, types, optionality,
array lengths, column stats, log templates, and a couple of samples —
instead of the content. A 2 MB JSON dump becomes twenty lines.

```
./structo.py FILE                summarize (format auto-detected:
                                 json/jsonl/yaml/csv/tsv/xml/log)
./structo.py FILE --path a.b[0].c    zoom into a JSON/YAML subtree
./structo.py FILE --sample N     array elements aggregated (default 10)
./structo.py FILE --max-tokens N cap output; samples go first, top-level
                                 structure never does
```

Everything streams — memory is O(schema + samples), never O(file), which
is test-enforced. Figures affected by sampling carry a `~` marker; clean
figures are exact. Output is plain text and deterministic (sampling is
first-N, no RNG).

Stdlib-only single file except YAML, which uses PyYAML's event API when
installed. `python -m pytest` from this directory runs the tests
(`-m "not slow"` skips the large-file memory test). See
[`DECISIONS.md`](DECISIONS.md) for the ADRs.
