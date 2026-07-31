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

## ADR-005: `--select` projects records as TSV; aggregation stays out — Accepted (2026-07-26)

Context: docs/known-issues/archive/structo-cannot-aggregate-across-jsonl-records.md
— answering "which tool runs net-negative?" over the suite's own
`.savings/events.jsonl` needed a group-by sum. structo could describe the
file's shape and address one record, but nothing in the suite could get at
the *values* across records, so the analysis fell back to four throwaway
Python scripts. The gap is self-inflicted and recurring: the same question
returns every time the savings record looks wrong.
Decision: add `--select f1,f2` — one TSV row per record, header line of the
literal field specs, fields addressed with the existing `--path` grammar
(`a.b`, `tags[0]`). Records are jsonl lines, a top-level JSON array or a
YAML sequence (or the array at `--path`), or CSV/TSV data rows. Aggregation
itself — `--group-by`, `--sum`, sorting — is explicitly *not* added: the
row stream pipes to `awk`/`sort`, which already do it and do it outside the
agent's context.
Consequences: structo gains a second output mode but no query language, and
the projection is a pure per-record map with no cross-record state, so
ADR-001 holds (memory is O(one record), test-enforced on a generated ~25 MB
JSON array). The cost is that the caller writes an `awk` line instead of a
flag — deliberate, since a query language inside structo would be the
twelfth tool the closed list (docs/decisions/0003) exists to prevent, and
the alternative reading of the issue ("this isn't structo's job at all")
would leave the gap open for a tool nobody is going to build.
TSV forces three encoding choices: a missing field is an empty cell while a
JSON `null` renders `null` (both coerce to 0 in `awk`, and the distinction
survives for callers who care); containers render as compact JSON; tabs and
newlines inside string values become spaces, because a row that breaks into
two rows silently corrupts whatever the caller sums. Line endings are
pinned to `\n` even on Windows — this output is machine-bound, not console
output. Like `--raw`, `--select` with `--max-tokens` refuses (exit 2)
rather than truncating: a projection that dropped records would corrupt the
downstream sum, and it measures in a first pass before printing so nothing
partial reaches stdout.

## ADR-006: `--max-tokens` defaults to 2000 for schema output; `--select`/`--raw` are exempt — Accepted (2026-07-31)

Schema output is capped by default at 2000 tokens. `--select` and `--raw`
are exempt from the *default* — never from an explicit `--max-tokens` —
because they feed `awk`/`sort` and refuse rather than truncate when over
budget (ADR-004, ADR-005). Defaulting them to a cap would turn an ordinary
`structo --select … | awk` into an error, which is a worse failure than the
one the cap prevents.

Fixed alongside: the ladder's deepest rung was "top-level keys only", which
is still one line per key and therefore unbounded for a wide record. A
4000-key object emitted ~12,800 tokens against `--max-tokens 200` — the
budget was not merely loose, it was ignored, in violation of INVARIANTS.
`render_schema` now takes a `key_cap`, and the ladder continues through
caps of 100, 40, 15 and 5 siblings with a `… (+N more keys)` note. The same
object now renders in ~150 tokens at that budget.

Suite-wide rationale and the measured evidence are in
`docs/decisions/0005-budgets-on-by-default.md`: across 661 logged calls in
the first 18 days of use, 1.4%% passed `--max-tokens`, while 3%% of calls
produced 8%% of all output. An opt-in cap protects only the caller who
already suspected the output would be large — the one who did not need
protecting.
