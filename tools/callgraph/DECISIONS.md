# callgraph Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Pure query layer — no parsing, ever — Proposed

Context: the suite's architecture puts all extraction in `repoindex`;
duplicating parsing here would fork the source of truth.
Decision: callgraph reads `.repoindex/index.db` (refs kind=call joined with
symbols) via stdlib sqlite3 and nothing else; graph gaps are repoindex bugs.
Consequences: the tool stays a few hundred lines; accuracy improvements land
in one place and benefit every query tool.

## ADR-002: Implicit index freshness via repoindex update — Proposed

Context: agents will not remember to rebuild an index; stale answers are
worse than slow ones.
Decision: check existence/staleness on every run and shell out to
`repoindex update` first (designed to be fast) before querying.
Consequences: runtime dependency on the repoindex CLI; first query after big
changes pays the update cost; answers are never knowingly stale.

## ADR-003: Uncertainty is rendered, not filtered — Proposed

Context: dynamic/duck-typed call edges are stored with
`confidence=heuristic`; hiding them lies, dropping the marker overclaims.
Decision: heuristic edges render with a trailing `?`; resolved edges clean;
no default filtering.
Consequences: agents can weigh uncertain edges themselves; output stays
honest about static-analysis limits.

## ADR-004: Disambiguation over guessing — Proposed

Context: bare names collide; silently picking one match sends agents down
wrong paths at high token cost.
Decision: multiple matches print a disambiguation list and exit; the agent
re-queries with the qualified name.
Consequences: one extra round-trip in the ambiguous case, zero misdirected
reports.
