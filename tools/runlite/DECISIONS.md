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

## ADR-005: `trace` is a subcommand, not a twelfth tool — Accepted (2026-08-07)

Context: a stack trace is the densest noise-to-signal artifact an agent
handles, but `runlite` only helps when it wrapped the command that produced
one. Traces also arrive from log files, CI, running services and pastes —
a distinct trigger. The suite's build list is closed at 11 tools
(docs/decisions/0003), and `rq`/`testmap` were archived for never being
reached for, so a new top-level tool is the expensive option.

Decision: add `runlite trace [FILE]` reading a file or stdin, reusing
runlite's existing job (drop the noise, keep the `path:line`) with a
different intake. Not a new tool directory, no new entry on the build list.

Consequences:

- Frames are normalized to innermost-first and chained exceptions to
  propagated-first, so output reads the same across five languages. Python
  is the one language needing both reversed; the chain marker names the
  relation *between* two exceptions, so it arrives attached to the later
  one and must be shifted onto the earlier one when reordered.
- Project-vs-library is the whole compression, and it is path-based where
  a path exists. Deliberately *not* kept: the innermost frame as such.
  Rust and Go put unwind machinery at frame 0, so "always keep the
  innermost" leads with `rust_begin_unwind` and buries the line that
  broke. The ends are kept only when nothing is project code.
- No "probable cause" field, though the idea that prompted this asked for
  one. That is inference, and the suite is offline and deterministic;
  a guessed cause carries no `path:line` and cannot be checked.
- Two-valued confidence does not apply — a frame is not a claim about a
  relationship, it is a line the runtime printed.
- Exit 1 means "no recognizable trace", distinct from 0. It cannot collide
  with a wrapped command's code because `trace` wraps nothing.
- Accepted limit: for JVM traces, library detection is package-prefix
  based and covers only what is structurally never your code (JDK, test
  runners, build tools). Third-party frames (Spring, Hibernate, …) render
  as project frames. Curating a framework list is the maintenance treadmill
  this suite rejected in the `depbrief` proposal; a false positive that
  shows a real `path:line` is the cheaper error.

## ADR-004: Budget rule — first failure full, rest one-liners — Accepted (2026-07-07)

Context: when many tests fail, the first failure is usually the root cause.
Decision: over `--max-tokens`, keep failure #1 complete and collapse the rest
to one line each.
Consequences: predictable output shape under pressure; later failures remain
discoverable via the raw log.
