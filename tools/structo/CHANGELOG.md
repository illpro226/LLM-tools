# structo Changelog

- 2026-09-24: v0.6.1 - a UTF-8 byte-order mark no longer corrupts data,
  silently. Every text read decoded as plain utf-8, so the BOM that Excel's
  "CSV UTF-8" and PowerShell 5's `Out-File` write stayed glued to the first
  field: a CSV's first header became `﻿id`, and `--select id` matched
  nothing and printed an empty column with exit 0; a JSONL file's record 0
  failed to parse and was skipped, so `--path "[0]"` answered with record 1
  and the summary under-counted records. TOML with a BOM failed as "Invalid
  statement", and a sniffed-as-TOML file that was not utf-8 escaped as a
  raw `UnicodeDecodeError` traceback (tomllib decodes strictly itself).
  All reads now go through `utf-8-sig` (identical on BOM-less files), TOML
  is decoded before `tomllib.loads`, and a non-utf-8 `.toml` is a clean
  "not valid toml" error while a sniffed one backs off to the log summary.
  Found by a suite review. 5 new tests (76 total; STATUS had drifted to 62).
- 2026-08-22: v0.6.0 - TOML is a supported format. `structo pyproject.toml`
  used to report `format: json (sniffed)` and emit character soup: the
  sniffer saw the leading `[` of a `[table]` header and handed the file to
  the JSON tokenizer, which is lenient enough to turn nonsense into a
  confident-looking shape. `.toml` now detects by extension, or by sniffing
  the first meaningful line (`[table]`/`[[array]]` header, or `key = <toml
  value>`), and parses via `tomllib` (stdlib 3.11+; `tomli` accepted as a
  fallback). It goes through `value_events`, so `--path`, `--raw` and
  `--select` (over an array of tables) work as they do for JSON/YAML, and
  TOML dates keep their own `datetime` scalar type instead of flattening to
  `str`. This is the one format parsed whole rather than streamed - tomllib
  has no event API and TOML is config-sized by construction (ADR-008). A
  file *sniffed* as TOML that fails to parse (ini/conf files share the
  `[section]` opener) falls back to the log summary; one named `.toml`
  exits 2 with the parse error rather than guessing. 9 new tests (71
  total). Closes docs/known-issues/structo-toml-sniffed-as-json.md.

- 2026-08-06: v0.5.0 - `--path "[-1]"` selects the last JSONL record, `[-2]`
  the one before it, and sub-paths compose (`[-1].tool`). Append-only logs
  are the normal case for JSONL - `events.jsonl`, session transcripts, ndjson
  exports - and the interesting record is the newest one, whose index you
  can't know without reading the file. `[N]` alone meant running structo
  once to learn the count and again to fetch the record. Stays streaming:
  a ring buffer holds the trailing |N| records, so memory is O(schema +
  samples + |N|), pinned by a test. The header resolves the index
  (`record -1 (1556)`), which answers "how many are there" in the same call.
  A negative anywhere else - inside a document, or in `--select` - is
  refused with the reason rather than silently reported as an absent path:
  arrays are walked as an event stream with no length known until they
  close, and buffering one would break the memory promise that is the point
  of streaming. 7 new tests (62 total). Closes
  docs/known-issues/archive/structo-path-no-negative-index.md.

- 2026-07-31: v0.4.0 — `--max-tokens` now defaults to 2000 for schema output
  (ADR-006, docs/decisions/0005-budgets-on-by-default.md); `--select` and
  `--raw` are exempt from the default (not from an explicit cap) so piping
  to `awk`/`sort` still works. Fixed: the degradation ladder bottomed out
  at one line per top-level key, so a wide record ignored any budget — a
  4000-key object emitted ~12,800 tokens against `--max-tokens 200`.
  `render_schema` gained a `key_cap` and the ladder continues through 100/
  40/15/5 siblings with a `… (+N more keys)` note; that object now renders
  in ~150 tokens. 5 new tests (55 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
- 2026-07-27: v0.3.1 — stdout pinned to UTF-8 so echoed values keep their
  non-ASCII characters on Windows (same fix as sgrep/repomap/gitbrief).
- 2026-07-26: v0.3.0 — `--select f1,f2` projects records as TSV, one row
  per record (ADR-005, from
  docs/known-issues/archive/structo-cannot-aggregate-across-jsonl-records.md).
  Records are jsonl lines, a JSON array / YAML sequence (top level or at
  `--path`), or CSV/TSV rows; fields use the `--path` grammar. Aggregation
  stays outside — the row stream pipes to `awk`/`sort`. Streaming preserved
  (memory O(one record), tracemalloc-enforced on a ~25 MB JSON array);
  `--select` + `--max-tokens` refuses rather than truncates. 13 new tests
  (50 total).
- 2026-07-12: v0.2.0 — JSONL record addressing and raw extraction
  (ADR-004, from docs/known-issues/archive/structo-jsonl-no-record-indexing.md).
  A leading `[N]` in `--path` zooms into JSONL record N; new `--raw`
  prints the exact value at `--path` (strings verbatim, else JSON) via a
  full-fidelity JSON tokenizer mode that still streams. `--raw` +
  `--max-tokens` refuses rather than truncates. 13 new tests (37 total).
- 2026-07-08: v0.1.0 — initial implementation. Single-file streaming CLI:
  format autodetection (extension + sniffing), incremental JSON event
  tokenizer, JSONL per-record merge, YAML via PyYAML events, CSV/TSV
  column stats, log template clustering, XML iterparse tree. `--path`
  zoom, `--sample`, `--max-tokens` staged degradation, `~` markers on
  sampled figures. 24 fixture tests incl. tracemalloc-enforced memory
  bound on a generated ~25 MB JSONL.
- 2026-07-06: Added initial documentation scaffold.
