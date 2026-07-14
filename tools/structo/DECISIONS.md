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

## ADR-004: JSONL record addressing and a raw-value mode — Accepted (2026-07-12)

Context: docs/known-issues/archive/structo-jsonl-no-record-indexing.md — there was
no way to zoom into record N of a JSONL file (`--path` matched inside every
record), and schema-only output made extraction tasks ("give me this one
string field") fall back to hand-written scripts.
Decision: a leading `[N]` path segment on a JSONL file selects record N
(the file as a virtual array; N counts parsed records, matching the
summary's record count), with the rest of the path applied inside it. A
new `--raw` flag prints the exact value at `--path`: strings verbatim,
everything else as JSON.
Consequences: on the rare JSONL whose records are themselves arrays, a
leading `[N]` no longer means "element N of each record" — record
addressing wins. Streaming (ADR-001) is preserved: JSONL raw parses one
line, JSON raw uses a full-fidelity tokenizer mode (`json_events(fh,
full=True)` — decoded escapes, uncapped strings) and materializes only the
target subtree, YAML events were lossless already. The schema path is
untouched (capped strings are fine for examples). `--raw` with
`--max-tokens` refuses with exit 2 instead of truncating — an exact value
can't be summarized harder, and truncating mid-value would violate the
suite output invariant; the cap keeps full force in schema mode.
