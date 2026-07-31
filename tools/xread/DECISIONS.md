# xread Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Regions as the common internal model — Accepted (2026-07-07)

Context: three modes (symbol, lines+scope, query) need one renderer with
headers, merging, elision, and budgets.
Decision: every mode resolves to `{file, start, end, score}` regions; the
renderer is mode-blind.
Consequences: merging/elision/budget logic is written and tested once; new
modes only need to produce regions.

## ADR-002: Blocks are the unit of trimming — Accepted (2026-07-07)

Context: `--max-tokens` must degrade gracefully, and half a function is worse
than no function for an agent.
Decision: budget cuts drop whole blocks (lowest score first) and trim at block
boundaries; never mid-statement.
Consequences: output at any budget is syntactically whole; worst case a
requested excerpt is omitted entirely rather than mangled.

## ADR-003: Stateless per-invocation parsing, no index — Accepted (2026-07-07)

Context: `repoindex` exists for relationship data; xread reads one or a few
files per call.
Decision: parse target files fresh each invocation with tree-sitter; no cache,
no index dependency.
Consequences: zero staleness concerns and no setup cost for users; large-file
re-parse cost is accepted (bounded by single-file scope).

## ADR-004: Stdlib parsers instead of tree-sitter — Accepted (2026-07-07)

Context: the planned design used tree-sitter + grammars, but the suite
invariants demand <100 ms startup and minimal dependencies, and tokq/runlite
set a stdlib-only precedent. tree-sitter grammar wheels are a heavy install
for what xread needs.
Decision: Python parses via stdlib `ast` (exact spans, decorators, attached
comments); JS/TS via a brace-tracking line scanner that strips
strings/comments and requires declarations to open their brace on the same
line; markdown via a fence-aware heading scan (headings are just another
symbol kind, per repo ADR-0001).
Consequences: zero dependencies and fast startup; Python spans are exact
while JS/TS spans are heuristic (Allman braces and multi-line arrow params
unsupported — acceptable, fixtures pin behavior). If tree-sitter is ever
justified, it slots in as an alternate `parser_for` backend without changing
the region model.

## ADR-005: `--max-tokens` defaults to 2000 — Accepted (2026-07-31)

An excerpt tool that can still emit an unbounded region unasked is only
excerpting by luck. The default is 2000 tokens against a measured 95th
percentile of ~1755; `--max-tokens 0` restores unbounded output.

Fixed alongside: when the sole surviving region had no blank line to trim
at, `apply_budget` dropped it entirely and returned only a
`(dropped for --max-tokens: …)` note. That is the one degradation that
answers no part of the question. It now halves the region toward its head
until it fits — a plain line boundary is worse than a paragraph boundary
and far better than nothing.

Suite-wide rationale and the measured evidence are in
`docs/decisions/0005-budgets-on-by-default.md`: across 661 logged calls in
the first 18 days of use, 1.4%% passed `--max-tokens`, while 3%% of calls
produced 8%% of all output. An opt-in cap protects only the caller who
already suspected the output would be large — the one who did not need
protecting.
