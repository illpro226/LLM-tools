# structo Roadmap

## M1 — Scaffold and detection — done (v0.1.0)

- CLI entry point, fixtures for every target format, test harness.
- Format detector (extension + sniffing) with detection tests.

## M2 — Tabular and JSON summarizers — done (v0.1.0)

- CSV/TSV: types, null rates, min/max, cardinality, 3 sample rows.
- JSON/JSONL: merged schema with types, optionality %, array-length stats,
  array sampling; streaming memory-bound test (tracemalloc, generated
  ~25 MB JSONL — scaled down from "multi-hundred-MB" to keep the suite
  fast; the bound is size-independent because parsing is per line).

## M3 — Remaining formats and zoom — done (v0.1.0)

- YAML (PyYAML events), XML (iterparse), and log summarizers (templates,
  timestamps, first/last lines).
- `--path` subtree zoom (json/jsonl/yaml); `--sample N`.

## M4 — Token budget — done (v0.1.0)

- `--max-tokens N` trimming samples → nesting depth → distribution detail;
  tests at descending budgets.

## M5 — Record addressing and value extraction — done (v0.2.0)

- `--path "[N]"` picks JSONL record N; `--raw` prints the exact value at
  `--path` instead of a schema (ADR-004).

## M6 — Projection — done (v0.3.0)

- `--select f1,f2` emits one TSV row per record for piping to `awk`/`sort`
  (ADR-005), covering jsonl, JSON arrays, YAML sequences and CSV/TSV.

## Later

- Parquet/compressed-input support if demand appears.
- Not planned: in-tool aggregation (`--group-by`/`--sum`) — decided
  against in ADR-005, not deferred.
