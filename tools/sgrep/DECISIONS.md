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
