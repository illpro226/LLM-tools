# structo Changelog

- 2026-07-08: v0.1.0 — initial implementation. Single-file streaming CLI:
  format autodetection (extension + sniffing), incremental JSON event
  tokenizer, JSONL per-record merge, YAML via PyYAML events, CSV/TSV
  column stats, log template clustering, XML iterparse tree. `--path`
  zoom, `--sample`, `--max-tokens` staged degradation, `~` markers on
  sampled figures. 24 fixture tests incl. tracemalloc-enforced memory
  bound on a generated ~25 MB JSONL.
- 2026-07-06: Added initial documentation scaffold.
