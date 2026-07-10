# codediff Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Symbol-level diffing on repoindex.extract — Proposed

Context: line diffs don't answer "what changed semantically"; the suite
already has one extraction implementation.
Decision: parse before (git blob) and after (worktree) versions with
`repoindex.extract`; align and diff at the symbol level. No second parser.
Consequences: hard dependency on repoindex as a library; language support
tracks repoindex's automatically.

## ADR-002: Deterministic and offline by default; LLM strictly additive — Proposed

Context: a review tool must be trustworthy in CI and reproducible; narrative
polish is optional.
Decision: the core pipeline is static analysis only. `--llm` (off by default)
sends the compact symbol-level delta — never raw hunks — for a one-paragraph
narrative.
Consequences: identical inputs give identical output; no keys or network in
the default path (test-enforced); the LLM can only rephrase, not decide.

## ADR-003: Explainable additive risk, never an opaque score — Proposed

Context: an unexplained HIGH is ignored or blindly obeyed — both bad.
Decision: risk is the sum of named signals (sensitive-path keywords from
`.codediff.toml`, public-API surface, behavior-delta size, tests-changed from
the shared `tests` table), and every contributing reason is printed.
Consequences: ratings are debatable line-by-line and tunable per repo;
"why HIGH?" is always answered in the output itself.

## ADR-004: Rename detection via body similarity — Proposed

Context: reporting a rename as remove+add doubles the apparent change and
misleads reviewers about API breakage.
Decision: unmatched before/after symbols with high body similarity pair as
renames in the API section.
Consequences: a similarity threshold to tune; fixtures pin its behavior on
the known-rename case.
