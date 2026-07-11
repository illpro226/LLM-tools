# 0002: Wave 4 is codediff alone; factbook and docsnip stay deferred

Status: Accepted (2026-07-10)

## Decision

With Waves 1–3 shipped and witnessed, Wave 4 un-defers exactly one tool:

- **Wave 4:** `codediff`

`factbook` and `docsnip` remain deferred. Nothing in 0001's rationale for
them has changed: factbook still duplicates agent-native memory for the
primary target agent, and docsnip's scope is still covered by docs MCP
channels while private infra docs are served by `sgrep` + `xread`'s
markdown mode.

`codediff` is buildable now precisely because its deferral was hedged: its
interface requirements on shared infrastructure were pinned before that
infrastructure was built (tools/repoindex/DECISIONS.md ADR-006), so no
refactor is needed to start.

## Amendments to the codediff PRD and START.md bootstrap prompt

Two instructions in the original spec are superseded by decisions made
after it was written:

1. **No tree-sitter.** The bootstrap prompt says to use repoindex's
   "tree-sitter machinery" for the before side. repoindex ADR-007 dropped
   tree-sitter suite-wide. Instead, `repoindex.extract(path, source)` is
   pure and filesystem-free (ADR-006) exactly so codediff can run it on
   git-blob content — the **same** extractor serves both the before and
   after sides. Deterministic qualnames are the before/after join key,
   already a tested guarantee in repoindex.

2. **No ordinal risk grade.** The PRD's `Risk: LOW/MED/HIGH` predates the
   suite invariant banning ordinal HIGH/MEDIUM/LOW scales
   (INVARIANTS.md, "Uncertainty is stored, not hidden — and not
   inflated"). The invariant's argument applies with equal force to an
   aggregate risk grade: the heuristics are honest, but the weighting that
   would collapse them into three buckets is not. codediff therefore
   reports risk as a flat list of deterministic, individually explainable
   flags (each with its evidence and `path:line`), plus a flag count —
   never a graded severity. The PRD acceptance criterion "Risk is HIGH
   for a fixture touching an auth path with no test changes" is amended
   to: that fixture must raise both the sensitive-path flag and the
   no-matching-test-change flag, each with its reason printed. Details in
   tools/codediff/DECISIONS.md.

## Consequences

- The 0001 build order is extended, not reopened: 0001's cut list stands
  except for codediff.
- codediff imports `repoindex.extract` as a library (repoindex ADR-002).
  That makes repoindex's extraction surface load-bearing for a second
  consumer; changes to `extract()`'s contract now affect two tools.
- Un-deferring factbook or docsnip later needs a new decision record with
  evidence that their 0001 deferral rationale no longer holds.
