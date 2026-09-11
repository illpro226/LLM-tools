# structo Testing

Fixture-based, per repo conventions (AGENTS.md). One fixture per supported
format, plus a large generated file for the streaming guarantee.

## Fixtures

- `tests/fixtures/` — `sample.json` (nested, optional keys, large array),
  `sample.jsonl`, `sample.yaml`, `sample.toml` (tables, an array
  of tables, a date), `sample.csv`, `sample.tsv`, `sample.xml`,
  `sample.log` (known timestamp format and repeated templates).
- Generators producing a ~25 MB JSONL and a ~25 MB single-array JSON on
  the fly for the memory-bound tests (summary and `--select` respectively;
  never committed; scaled down from the planned multi-hundred-MB —
  the bound is size-independent since parsing is per line, and the suite
  stays fast).

## Test areas

- **Detection** — each fixture detected correctly by extension and, with
  extensions stripped, by content sniffing.
- **JSON/YAML** — merged schema: types, optionality percentages, array-length
  stats; arrays past `--sample N` are sampled and labeled as estimates.
- **TOML** — schema, `--path`, `--raw` and `--select` over an array of
  tables; dates render as their own `datetime` type. Detection guards both
  ways: a `[table]` header sniffs as TOML rather than JSON (the bug that
  motivated support), while `.env`-style `FOO=bar` and ini files that
  `tomllib` rejects fall back to the log summary. An invalid `.toml`
  exits 2 with the parse error and nothing on stdout.
- **CSV/TSV** — per-column type, null rate, min/max, cardinality; exactly 3
  sample rows.
- **Logs** — timestamp format detected; line count exact; top templates
  cluster ids/numbers correctly; first/last lines present.
- **Zoom** — `--path a.b[0].c` summarizes only the subtree; invalid path
  yields a short error and nonzero exit.
- **Projection** — `--select` emits header + one row per record for jsonl,
  JSON arrays (top level and at `--path`), YAML sequences and CSV/TSV;
  dotted/indexed fields, missing vs `null` cells, container cells, tab and
  newline scrubbing, unparsable lines skipped as in the summary; every
  error path (with `--raw`, jsonl with `--path`, non-array target, missing
  path, non-record format, empty field) exits 2 with *nothing* on stdout.
- **Streaming** — peak memory stays bounded (O(schema+samples), and
  O(one record) under `--select`) on the generated large files, asserted
  via resource tracking.
- **Token cap** — trimming order: sample records → deep nesting collapse →
  distribution detail; top-level structure always survives. `--select`
  refuses over budget (exit 2, no partial output) and prints every row
  under it.
- **Determinism** — identical output across repeated runs for every fixture
  (sampling is first-N, no RNG — ADR-003 as amended).

## Running

`python -m pytest` from `tools/structo/` (50 tests). The two memory tests
are marked `slow` (`-m "not slow"` skips them); YAML tests skip when PyYAML
is absent.
