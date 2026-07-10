# structo Status

Implemented (v0.1.0) and passing tests.

- `structo.py` — single-file CLI printing the schema and shape of a data
  file instead of its content. Formats: JSON, JSONL, YAML (via PyYAML —
  the one optional dependency, with a clear error if absent), CSV, TSV,
  XML, generic log. Detection by extension, else content sniffing; the
  header states which.
- Streaming throughout (ADR-001): JSON via an incremental event tokenizer
  (no `json.load` on whole files), JSONL per record, YAML via the PyYAML
  event API, CSV per row, logs per line, XML via `iterparse` with element
  clearing. Memory is O(schema + samples) — test-enforced with
  tracemalloc on a generated ~25 MB JSONL (peak < 15 MB asserted).
- JSON/YAML/JSONL: merged schema with types, optionality percentages
  (key presence / parent object instances), array length stats (always
  exact); array *elements* beyond `--sample N` (default 10) are not
  aggregated and the line carries a `~` marker (ADR-003 — sampling is
  first-N, deterministic, no RNG). One or two example values per scalar.
- CSV/TSV: per-column type, null rate, min/max (numeric or lexicographic;
  omitted for booleans), cardinality (bounded distinct counter, `~` past
  256), exactly 3 sample rows.
- Logs: timestamp format (iso-8601/syslog/clf/epoch), exact line count,
  top message templates (numbers/hex/uuids/quoted strings normalized,
  bounded table), first/last lines with `path:line` refs.
- `--path a.b[0].c` zooms into a JSON/YAML subtree (per record for
  JSONL); unmatched paths exit 2.
- `--max-tokens N` (bytes/4) degrades by whole levels: drop
  examples/sample rows → collapse deep nesting and distribution detail →
  top-level structure only (never dropped).
- Tests: `tests/test_structo.py` (24 tests) over one committed fixture
  per format plus the generated large file (slow-marked).

Not done / later: XML has no `--path` zoom; no Parquet/compressed inputs;
YAML support requires PyYAML (yaml tests skip without it).
