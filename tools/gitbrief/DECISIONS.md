# gitbrief Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Subprocess plumbing only, no libgit — Accepted (2026-07-08)

Context: the PRD mandates pure `git` subprocess calls; libgit bindings add a
heavy dependency and a second behavior surface.
Decision: one runner helper invoking git with explicit argv, color disabled,
and stable porcelain formats (`status --porcelain=v2`, `diff --numstat`,
`log --format=…`, `rev-list --left-right --count`).
Consequences: zero binary dependencies beyond git itself; every data fetch is
a reproducible command line; human-oriented git output is never parsed.

## ADR-002: Layered disclosure as the product shape — Accepted (2026-07-08)

Context: the token sink is agents dumping full diffs by default.
Decision: default view is the one-screen summary; `hunks` adds headers;
`show` (single file) is the only full-diff path.
Consequences: the expensive view requires an explicit, narrow request;
"show me everything" is deliberately not a mode.

## ADR-003: tree-sitter is optional enhancement only — Superseded by ADR-005

Context: `pr` wants changed-symbol lists, but gitbrief must work anywhere git
does.
Decision: import tree-sitter lazily inside `pr`; on failure, omit the symbol
section with a one-line note.
Consequences: no hard parser dependency; symbol lists are best-effort and the
omission is visible rather than silent.

## ADR-004: Strictly read-only — Accepted (2026-07-08)

Context: a state summarizer that mutates state is a hazard for agents.
Decision: no mode stages, commits, or touches the worktree; enforced by a
repo-state-equality test around every mode.
Consequences: gitbrief is always safe to run; write workflows stay with git.
As built: every git call also passes `--no-optional-locks`, so even
`status` cannot opportunistically rewrite the index.

## ADR-005: Changed symbols via stdlib blob extraction — Accepted (2026-07-08)

Context: ADR-003 planned tree-sitter as an optional import for `pr`
symbol lists, but the suite has since settled on stdlib parsers (xread
ADR-004, repomap ADR-004) — an optional heavy dependency for one
subcommand contradicts that precedent, and "works only if tree-sitter
happens to be installed" makes output machine-dependent.
Decision: `pr` extracts top-level symbols from the before/after blobs
(`git show REV:path`) with stdlib parsers — Python via `ast`, JS/TS via a
brace-tracking scanner — and classifies +added / ~modified / -removed by
intersecting symbol spans with `-U0` diff ranges. Other languages appear
in a "not analyzed" note; the section is labeled heuristic.
Consequences: symbol lists are always available and deterministic with
zero dependencies; language coverage is narrower than tree-sitter would
give (extendable file-by-file); the omission note keeps the gap visible
rather than silent.

## ADR-006: `--max-tokens` defaults to 2000 — Accepted (2026-07-31)

`hunks` on a large working diff is exactly the call that floods a context
window, and never the call anyone thinks to guard — the diff is big
*because* the work went well. On this repo the default takes `gitbrief
hunks` from ~2,900 tokens to ~310. `--max-tokens 0` restores unbounded
output.

Suite-wide rationale and the measured evidence are in
`docs/decisions/0005-budgets-on-by-default.md`: across 661 logged calls in
the first 18 days of use, 1.4%% passed `--max-tokens`, while 3%% of calls
produced 8%% of all output. An opt-in cap protects only the caller who
already suspected the output would be large — the one who did not need
protecting.
