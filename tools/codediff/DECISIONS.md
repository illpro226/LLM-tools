# codediff Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Symbol-level diffing on repoindex.extract — Accepted

Context: line diffs don't answer "what changed semantically"; the suite
already has one extraction implementation.
Decision: parse before (git blob) and after (worktree) versions with
`repoindex.extract`; align and diff at the symbol level. No second parser.
Consequences: hard dependency on repoindex as a library; language support
tracks repoindex's automatically.

## ADR-002: Deterministic and offline by default; LLM strictly additive — Accepted (amended by ADR-005)

Context: a review tool must be trustworthy in CI and reproducible; narrative
polish is optional.
Decision: the core pipeline is static analysis only. `--llm` (off by default)
sends the compact symbol-level delta — never raw hunks — for a one-paragraph
narrative.
Consequences: identical inputs give identical output; no keys or network in
the default path (test-enforced); the LLM can only rephrase, not decide.

## ADR-003: Explainable flat risk flags, never a score or grade — Accepted (amended per docs/decisions/0002)

Context: an unexplained severity rating is ignored or blindly obeyed — both
bad; the suite invariant bans ordinal scales outright.
Decision: risk is a flat list of named, independent flags (sensitive-path
keywords from `.codediff.toml`, public-API surface, behavior-delta size,
stale/missing test coverage from the shared `tests` table), each printed
with its reason and `path:line`. Nothing is summed, weighted, or graded.
Consequences: every flag is debatable line-by-line and tunable per repo;
"why is this flagged?" is always answered in the output itself, and no
aggregate exists to be gamed or misread.

## ADR-004: Rename detection via body equality, not fuzzy similarity — Accepted (amended)

Context: reporting a rename as remove+add doubles the apparent change and
misleads reviewers about API breakage.
Decision: unmatched before/after symbols of the same kind pair as a rename
when their normalized bodies below the header are nontrivial and exactly
equal. The originally proposed fuzzy similarity threshold was dropped: a
tunable threshold is an ordinal confidence scale in disguise (the same
argument as INVARIANTS.md's two-valued confidence rule), and exact
equality is deterministic and explainable.
Consequences: rename+edit in one change reports as remove+add — an honest
under-claim rather than a probabilistic guess; the fixture pins the
pure-rename case.

## ADR-005: No `--llm` flag; `--json` is the narrator payload — Accepted

Context: the PRD lists `--llm` for an optional one-paragraph narrative.
No other shipped tool in the suite grew an LLM flag, and the primary
consumer is itself an LLM agent reading stdout.
Decision: drop `--llm`. The compact symbol-level delta ADR-002 says an LLM
may receive is exactly the `--json` document; a narrator pipes that
wherever it wants. The core tool stays keyless and networkless
(test-enforced by a socket double).
Consequences: PRD's `--llm` criterion is satisfied vacuously (no network,
ever); if an in-tool narrative is wanted later it wraps the existing JSON,
adding no new analysis path.
