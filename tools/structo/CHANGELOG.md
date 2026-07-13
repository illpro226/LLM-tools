# structo Changelog

- 2026-07-12: v0.2.0 — JSONL record addressing and raw extraction
  (ADR-004, from docs/known-issues/structo-jsonl-no-record-indexing.md).
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
