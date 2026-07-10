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

## Later

- Parquet/compressed-input support if demand appears.
