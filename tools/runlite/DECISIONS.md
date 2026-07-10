# runlite Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Extractors are pure text functions in a registry — Accepted (2026-07-07)

Context: many tools to support, more to come; tests must not require real
toolchains.
Decision: each extractor declares a matcher (command name and/or log
fingerprint) plus a parse function over captured text; registered in a list.
Consequences: adding a tool is one module; fixtures are canned logs; detection
order (name → fingerprint → generic) is explicit and testable.

## ADR-002: Heuristic extraction with the raw log as escape hatch — Accepted (2026-07-07)

Context: perfectly parsing every tool's output format is unwinnable.
Decision: favor "always show something useful" heuristics; `--full-log PATH`
preserves the complete log for drill-in with `xread`.
Consequences: occasional imperfect extraction is acceptable and recoverable;
the generic fallback (error-pattern lines + last 20) guarantees a floor.

## ADR-003: Exit-code passthrough — Accepted (2026-07-07)

Context: agents and scripts branch on exit codes.
Decision: runlite exits with the wrapped command's code, not its own success.
Consequences: composes in `&&` chains and CI; runlite's own failures must use
a distinguishable reserved code.

## ADR-004: Budget rule — first failure full, rest one-liners — Accepted (2026-07-07)

Context: when many tests fail, the first failure is usually the root cause.
Decision: over `--max-tokens`, keep failure #1 complete and collapse the rest
to one line each.
Consequences: predictable output shape under pressure; later failures remain
discoverable via the raw log.
