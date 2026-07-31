# structo Changelog

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
