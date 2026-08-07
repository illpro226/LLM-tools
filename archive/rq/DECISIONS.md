# rq Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Subcommand-per-question, ~20 lines each — Accepted

Context: the index makes many questions nearly free; the risk is each answer
growing bespoke machinery.
Decision: every subcommand is a flat function returning rows from one or two
SQL queries; freshness, budgets, JSON, and citation formatting live in shared
plumbing. A subcommand passing ~50 lines signals logic that belongs in the
index or the plumbing.
Consequences: the marginal question stays cheap; the shared plumbing is the
only place output conventions are implemented.
Confirmed in implementation: every subcommand returns `(groups, notes,
status)` to one shared `render()`; the two that exceed ~20 lines (`impact`,
`deadcode`) are pure query-and-filter, no formatting.

## ADR-002: No parsing — data gaps are repoindex's to fix — Accepted

Context: same suite invariant as `callgraph`.
Decision: stdlib sqlite3 reads only; rq never opens a source file.
Consequences: rq stays thin; wrong answers are index bugs, fixed once for all
query tools. Confirmed concretely: the fixture's Python ABC registers no
`inherits` edge for `Shape` (repoindex converts it to `implements`), so
`rq inherits Shape` finds nothing — that is correct rq behavior, not a bug
to patch around with parsing.

## ADR-003: Graph algorithms split between SQL and in-process — Accepted (amended)

Context: closures and SCCs are graph work; SQLite has recursive CTEs but not
everything is natural there.
Decision as proposed: transitive closure (`impact`) as a depth-capped
recursive CTE; SCCs (`findcycles`) via Tarjan in-process over edges fetched
once.
Amended in implementation: `impact` is a per-level SQL BFS, not a recursive
CTE. Each discovered ref must be joined to its innermost enclosing symbol
(`ORDER BY line_start DESC, span ASC LIMIT 1` per ref) to name the dependent,
and that correlated innermost-match cannot be expressed inside a recursive
CTE. The BFS issues one small query set per level, capped by `--depth`, so
the cost profile is the same. `findcycles` is iterative Tarjan as proposed,
over import edges resolved to files by stem within one language family.
Consequences: each algorithm uses its clearest formulation; both are
deterministic and testable against fixture ground truth.

## ADR-004: deadcode is conservative by default — Accepted

Context: "zero inbound refs" over static data has false positives (dynamic
dispatch, reflection, external callers of exported API).
Decision: exported symbols are excluded unless `--include-exported`; the
confidence caveat prints whenever heuristic refs exist in the index.
Consequences: default output is safe to act on; the aggressive view is an
explicit opt-in. Implementation also excludes dunders (called implicitly by
the runtime), symbols in test files (invoked by the runner), names matched
by any heuristic ref, and names appearing as inherits-parents or
implements-interfaces — heuristic name matching is deliberately
cross-language within a family, accepting misses over false accusations.

## ADR-005: Token budget collapses uniformly via item caps — Accepted

Context: INVARIANTS.md requires `--max-tokens` to degrade by summarizing
harder, never truncating mid-thought; rq output is lists of claim lines
under group titles.
Decision: rendering retries with a per-group item cap descending from the
largest group until the estimate (bytes/3.7, tokq's fallback heuristic)
fits; omitted items become one `(+N more)` line per group (`"omitted": N`
in JSON). The floor is titles plus counts — rq never drops the fact that
matches exist.
Consequences: shown items are always a prefix of the full deterministic
ordering; a budget too small for even the floor still yields complete
counts.

## ADR-006: publicapi prints kind + location, not signatures — Accepted

Context: the PRD sketched exported symbols "with signatures", but the
repoindex schema stores no signature text — only qualname, kind, span,
exported.
Decision: print `path:line  qualname  kind` and nothing invented; adding
signatures is a repoindex schema change (per ADR-002 the gap belongs
there), after which rq picks them up with a one-line format change.
Consequences: no second parser and no stale signature cache in rq; callers
needing the exact signature follow the `path:line` with `xread`.
