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

## ADR-006: Test files get their own counted section — Accepted

Context: dogfooding on a change that added one CLI subcommand plus 29 tests
put every new test function under **API changes**, one line each, with the
single genuinely new piece of public surface as the last line of the section
(docs/known-issues/codediff-enumerates-every-new-test.md). The section was
accurate by a literal reading — those are newly added top-level functions —
but the noise scaled with test count, so the better-tested the change, the
worse the summary. Signal ordering is the whole product.
Decision: "API" means a surface a caller could depend on, and nothing depends
on a test name. Files matching the existing `_is_test_path` conventions
(`tests/**`, `test_*`, `*_test.py|go`, `*.test.*`, `*.spec.*`) bypass
symbol-level classification entirely and emit one line in a new **Tests**
section: added/removed/changed counts split into test functions and helpers
(`+29 tests, +1 helper`). Mechanical detection still runs first, so a
reformatted test file stays Mechanical.
Consequences: test symbols cannot reach the API/Behavior lists, so they no
longer inflate the public-API or behavior-delta risk flags — a well-tested
change stops reading as a riskier one. The cost is that a semantically
interesting edit to a test helper is reported only as a count; the file and
its `path:line` are still listed, so `xread`/`gitbrief` can follow up. No new
flag to exclude tests is needed, and none was added.

## ADR-007: `--max-tokens` defaults to 3000; `--json` stays full — Accepted (2026-07-31)

A pre-commit summary is read while the context already holds the work that
produced the diff, so it is the worst moment to spend thousands of tokens
unasked. The default is 3000 against a measured 95th percentile of ~3281.

`--json` is exempt from the default and from any cap: it is the narrator
payload (ADR-005), and a truncated payload is not parseable. `--max-tokens
0` restores unbounded text output.

Suite-wide rationale and the measured evidence are in
`docs/decisions/0005-budgets-on-by-default.md`: across 661 logged calls in
the first 18 days of use, 1.4%% passed `--max-tokens`, while 3%% of calls
produced 8%% of all output. An opt-in cap protects only the caller who
already suspected the output would be large — the one who did not need
protecting.
