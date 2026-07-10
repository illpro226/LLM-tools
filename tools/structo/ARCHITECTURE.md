# structo Architecture

Status: implemented (v0.1.0) as a single file, `structo.py` (stdlib;
PyYAML optional for YAML).

## Overview

`structo` detects the format, streams the file through a format-specific
summarizer that maintains bounded state, and renders a shape report.
Nothing is ever fully materialized in memory.

```
detect(extension, head bytes) ──► format
stream(file) ──► summarizer (bounded state)
model ──► render(level)*  ──► fit(levels, budget) picks the report
```

## Components

- **Format detector** (`detect`) — extension hint, else content sniffing
  on the first 8 KB (XML `<`, JSON vs JSONL by parsing the first two
  lines, delimiter-count consistency for CSV/TSV, `key:` / `---` for
  YAML, log fallback; binary input is an error). The header names which
  path decided.
- **One event vocabulary for JSON/JSONL/YAML** — `("{",) ("}",) ("[",)
  ("]",) ("key", k) ("scalar", type, text)` produced by three sources:
  an incremental chunk-fed JSON tokenizer (`json_events`), synthetic
  events from per-line `json.loads` records (`value_events`), and the
  PyYAML event API (`yaml_events`).
- **Schema driver** (`Shape`) — consumes events against a merged schema:
  key → {type counts, presence count}, arrays → exact length stats with
  only the first `--sample N` elements schema-merged (`sampled ~` flag),
  scalars → up to 2 example values. `--path a.b[0].c` is matched during
  the same pass; only the addressed subtree feeds the schema (JSONL:
  per record).
- **CSV/TSV summarizer** — per-column type inference, null rate, min/max
  (numeric or lexicographic; skipped for booleans), bounded distinct
  counter (cap 256, `~` past it), first 3 rows retained.
- **Log summarizer** — timestamp-format detection on the first line,
  exact line count, message templates (uuid/hex/number/quoted-string
  normalization, bounded table of 512), first/last lines with
  `path:line`.
- **XML summarizer** — `iterparse` tag tree with element counts,
  attribute counts, and text presence; `elem.clear()` keeps memory flat.
- **Renderer / budget** (`fit`) — each format exposes render levels from
  most to least detailed; the first within `--max-tokens` (bytes/4) wins.
  Trim order: examples/sample rows → nesting depth + distribution detail
  → top-level structure only (never dropped).

## Key decisions

- Streaming is a hard requirement (ADR-001): memory is
  O(schema + samples), enforced by a tracemalloc test on a generated
  ~25 MB JSONL.
- Sampling honesty (ADR-003): first-N, deterministic; `~` marks every
  figure a cap or sample touched. Lengths and line counts stay exact.
- One summarizer per format behind a common shape (ADR-002, amended:
  JSON/JSONL/YAML share the event vocabulary and one driver).

## Dependencies

Stdlib; `PyYAML` only for YAML input (clear error when absent).
