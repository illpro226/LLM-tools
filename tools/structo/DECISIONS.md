# structo Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Streaming is a hard requirement — Accepted (2026-07-08)

Context: the tool exists because agents cat multi-MB files; loading them fully
would reproduce the problem in memory.
Decision: every summarizer implements `feed`/`finish` over chunks/records with
bounded state; memory is O(schema + samples), never O(file).
Consequences: incremental parsers only (no `json.load` on whole files);
a resource-tracked test enforces the bound.

## ADR-002: One summarizer per format behind one interface — Accepted (2026-07-08), amended

Context: six formats now, more possible (Parquet, compressed inputs).
Decision: format detection dispatches to a per-format module sharing the
`feed`/`finish` interface and a common shape-model output.
Consequences: adding a format is one module; the renderer and budget logic
stay format-blind.
As built: the interface settled on "summarizer function → model +
render(level) closures" rather than feed/finish objects, and JSON, JSONL,
and YAML share one event vocabulary and one schema driver (`Shape`), so
those three are a single summarizer behind three event sources. The
budget logic (`fit`) is format-blind as planned; renderers are per-format.

## ADR-003: Sampled figures are labeled, not passed off as exact — Accepted (2026-07-08), amended

Context: sampling large arrays trades accuracy for cost; agents must not
mistake estimates for counts.
Decision: sampled/estimated values render with a `~` marker; exact values
render clean. Sampling is seeded for deterministic output.
Consequences: slight output noise, but downstream reasoning stays honest and
runs stay reproducible.
As built: sampling is first-N rather than seeded-random — simpler, order-
stable, and every bit as deterministic; array *lengths* are always exact
because elements past the sample are still counted, only their schema
merge is skipped. The `~` marker also covers the capped distinct counter
(CSV) and the capped template table (logs).
