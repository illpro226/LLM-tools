# sgrep Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Wrap ripgrep, never reimplement matching — Accepted (2026-07-07)

Context: matching is a solved problem; the value here is condensing.
Decision: shell out to `rg --json` and post-process the event stream;
missing binary is a first-class error path, not a fallback matcher.
Consequences: runtime dependency on ripgrep; in exchange, sgrep inherits rg's
speed, correctness, and ignore-file handling for free.

## ADR-002: Dedupe by normalized line content — Accepted (2026-07-07)

Context: the biggest waste in grep dumps is near-identical hits (same call
site pattern repeated).
Decision: cluster matches per file by normalized text (collapse whitespace,
strip numbers/ids); show the 3 most distinct when count > 5, plus a
`(+N more similar)` remainder.
Consequences: some genuinely distinct hits may cluster; the remainder count
keeps the information loss visible and recoverable via raw `rg`.

Amended 2026-09-24 (v0.6.0): the fixed "3 most distinct" cap is gone; every
cluster gets a representative and ADR-003's budget ladder does the capping.
The cap wasn't deduplication: normalization had kept six different JSON keys
as six clusters, but sgrep still showed three and called the rest "similar",
hiding the one key being searched for in a 6-line result. When the budget
does cap distinct clusters away, the footer says `(+N more, D distinct)`.
Over-budget output is unchanged, since the ladder's first per-file cap is
still 3.

## ADR-003: Fixed reduction order for --max-tokens — Accepted (2026-07-07)

Context: budget cuts must be predictable for agents.
Decision: reduce context lines, then matches per file, then files shown — in
that order, re-rendering until within budget.
Consequences: at tight budgets output converges toward `--counts-only`;
behavior is testable at each stage.

## ADR-004: Deliberately small flag surface — Accepted (2026-07-07)

Context: rg has hundreds of flags; mirroring them couples us to its interface.
Decision: expose pattern, paths, and a safe pass-through subset only; power
users fall back to raw `rg`.
Consequences: simpler tool and tests; some rg workflows are out of scope.

## ADR-005: `--max-tokens` defaults to 1500 — Accepted (2026-07-31)

`sgrep` is the most-called tool in the suite and the cheapest per call, so
its cap is the tightest: 1500 tokens, against a measured 95th percentile of
~990. `--max-tokens 0` restores unbounded output.

Because the ladder drops context first (ADR-003), the reduction is now
announced: `(context reduced 3 -> 1 for --max-tokens 1500)`. Silently
serving fewer context lines than `-C` asked for would read as *absent*
context — the caller would conclude the surrounding lines don't exist,
rather than that they were trimmed, and would never think to raise the cap.

Suite-wide rationale and the measured evidence are in
`docs/decisions/0005-budgets-on-by-default.md`: across 661 logged calls in
the first 18 days of use, 1.4%% passed `--max-tokens`, while 3%% of calls
produced 8%% of all output. An opt-in cap protects only the caller who
already suspected the output would be large — the one who did not need
protecting.
