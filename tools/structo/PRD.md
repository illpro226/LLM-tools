# structo PRD

## Problem statement

Agents frequently `cat` a 2 MB JSON or CSV file just to learn its structure, paying an enormous token cost for information that fits in twenty lines. `structo` prints the schema and shape of a data file — keys, types, nesting, row counts, distributions, and a couple of samples — instead of the content.

## Target users

- Coding agents inspecting data files, API dumps, exports, and logs.
- Humans doing quick exploratory looks at unfamiliar data files.

## Scope

### Core behavior

- Detect the input format: JSON, JSONL, YAML, CSV/TSV, XML, or generic log.
- JSON/YAML: print an inferred schema with types, optionality percentages, and array lengths; sample large arrays instead of walking them fully.
- CSV/TSV: columns with inferred types, null rates, min/max, cardinality, and 3 sample rows.
- Logs: detected timestamp format, line count, top repeated message templates (clustered by stripping numbers/ids), and first/last lines.
- Stream all inputs — never load a file fully into memory.

### CLI surface

- `structo FILE` — summarize a file (format auto-detected).
- `--path a.b[0].c` — zoom into a JSON/YAML subtree.
- `--sample N` — control sample size.
- `--max-tokens N` — cap output; degrade by reducing samples and collapsing deep nesting before dropping top-level structure.

## Non-goals

- Full statistical profiling or data-quality reporting.
- Transforming, querying, or extracting data values (use `jq`/`xread`-style tools).
- Source-code summarization (that is `repomap`/`xread`).

## Acceptance criteria

- Each supported format is auto-detected from fixture files and produces the format-appropriate summary described above.
- JSON schema output reports types, optionality percentages, and array lengths, with large arrays sampled.
- CSV output includes per-column type, null rate, min/max, cardinality, and exactly 3 sample rows.
- Log output includes timestamp format, line count, top message templates, and first/last lines.
- `--path` zooms into the named subtree; invalid paths produce a short error.
- Memory stays bounded on a large fixture (streaming verified).
- `--max-tokens` keeps output within budget.
- Fixture tests exist for every supported format.
