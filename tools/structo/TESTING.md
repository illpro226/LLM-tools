# structo Testing

Fixture-based, per repo conventions (AGENTS.md). One fixture per supported
format, plus a large generated file for the streaming guarantee.

## Fixtures

- `tests/fixtures/` — `sample.json` (nested, optional keys, large array),
  `sample.jsonl`, `sample.yaml`, `sample.csv`, `sample.tsv`, `sample.xml`,
  `sample.log` (known timestamp format and repeated templates).
- A generator producing a ~25 MB JSONL on the fly for the memory-bound
  test (never committed; scaled down from the planned multi-hundred-MB —
  the bound is size-independent since parsing is per line, and the suite
  stays fast).

## Test areas

- **Detection** — each fixture detected correctly by extension and, with
  extensions stripped, by content sniffing.
- **JSON/YAML** — merged schema: types, optionality percentages, array-length
  stats; arrays past `--sample N` are sampled and labeled as estimates.
- **CSV/TSV** — per-column type, null rate, min/max, cardinality; exactly 3
  sample rows.
- **Logs** — timestamp format detected; line count exact; top templates
  cluster ids/numbers correctly; first/last lines present.
- **Zoom** — `--path a.b[0].c` summarizes only the subtree; invalid path
  yields a short error and nonzero exit.
- **Streaming** — peak memory stays bounded (O(schema+samples)) on the
  generated large file, asserted via resource tracking.
- **Token cap** — trimming order: sample records → deep nesting collapse →
  distribution detail; top-level structure always survives.
- **Determinism** — identical output across repeated runs for every fixture
  (sampling is first-N, no RNG — ADR-003 as amended).

## Running

`python -m pytest` from `tools/structo/`. The memory test is marked `slow`
(`-m "not slow"` skips it); YAML tests skip when PyYAML is absent.
