# structo Status

Implemented (v0.5.0) and passing tests.

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
  JSONL; a leading `[N]` picks JSONL record N instead — ADR-004);
  unmatched paths and out-of-range records exit 2. `[-1]` is the last
  record (ring buffer of the trailing |N|, so streaming holds); a negative
  index anywhere else is refused with the reason, since arrays inside a
  document have no known length until they close.
- `--raw` prints the exact value at `--path` instead of a schema:
  strings verbatim, everything else as JSON. Still streaming — JSONL
  parses one line, JSON uses a full-fidelity tokenizer mode that
  materializes only the target subtree. With `--max-tokens` it refuses
  (exit 2) rather than truncates (ADR-004).
- `--select f1,f2` prints one TSV row per record instead of a schema —
  header line of the field specs, then the values (ADR-005). Records are
  jsonl lines, a top-level JSON array / YAML sequence or the array at
  `--path`, or CSV/TSV data rows; fields use the `--path` grammar
  (`a.b`, `tags[0]`). Missing fields are empty cells, JSON `null` renders
  `null`, containers render as compact JSON, and tabs/newlines inside
  values become spaces so a row is always one row. Line endings are `\n`
  on every platform. Streams like everything else (memory O(one record)).
  With `--max-tokens` it refuses (exit 2) rather than drops records, and
  measures before printing so nothing partial reaches stdout. Aggregation
  is deliberately absent — pipe to `awk`/`sort`:
  `structo events.jsonl --select tool,bytes | awk -F'\t' 'NR>1{s[$1]+=$2}...'`
- `--max-tokens N` (bytes/4) degrades by whole levels: drop
  examples/sample rows → collapse deep nesting and distribution detail →
  top-level structure only (never dropped).
- `--max-tokens` defaults to 2000 for schema output rather than unbounded
  (ADR-006, docs/decisions/0005). `--select` and `--raw` are exempt from
  the *default* but not from an explicit cap, so piping to `awk`/`sort`
  keeps working; `--max-tokens 0` restores unbounded output everywhere.
- The ladder ends in sibling-key caps (100/40/15/5 with `… (+N more
  keys)`), so a very wide record still fits a budget — depth levels alone
  bottomed out at one line per top-level key (ADR-006).
- Tests: `tests/test_structo.py` (62 tests) over one committed fixture
  per format plus the generated large files (slow-marked).

Not done / later: XML has no `--path` zoom and no `--select`; no
Parquet/compressed inputs; YAML support requires PyYAML (yaml tests skip
without it). Aggregation (`--group-by`/`--sum`) is a decided no, not a
backlog item (ADR-005).
