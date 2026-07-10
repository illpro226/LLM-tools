# testmap Decisions

ADR log.

## ADR-001: Layered union, tagged by source — Accepted

Context: no single mapping heuristic is both cheap and complete.
Decision: run convention, import, and coverage layers; union results, each
tagged with the layer that produced it; when several layers find the same
(test, target) pair, the most-trusted tag wins (coverage > changed-test >
convention > import).
Consequences: callers see *why* a test was selected; precision improves as
cheaper layers are corroborated by coverage without ever blocking on it.
Note: repoindex's seeder records a pair that matches both by name and by
import as its `import` link, so a spec file importing its subject shows
`(import depth 1)`, not `(convention)`.

## ADR-002: Coverage rows live in repoindex's tests table — Accepted

Context: `codediff` and `rq untested` want the same test-coverage
relationships; a private store would fragment them.
Decision: `testmap record` writes into `.repoindex/index.db` `tests` with
`source=coverage`; testmap owns no storage. Companion change on the
repoindex side: `update`'s derived-row rebuild now preserves coverage rows
(they are recorded facts, not re-derivable), dropping them only when their
test file changes or either endpoint leaves the repo.
Consequences: one shared source of truth (suite invariant); testmap's
record path depends on the repoindex schema being present.

## ADR-003: Best-effort scoping, full suite as explicit fallback — Accepted

Context: static mapping cannot be provably complete (dynamic imports,
fixtures, conftest side effects).
Decision: present the mapped set as the recommended scope, never claim
completeness; the full-suite command remains the caller's fallback and is
printed when nothing maps. Indexed changed files that mapped to no test
are noted individually.
Consequences: occasional missed tests are an accepted trade for the
token/time savings; coverage recording narrows the gap over time.

## ADR-004: Depth-limited transitive imports, default 2 — Accepted

Context: unlimited transitive closure over imports converges on "run
everything", defeating the tool.
Decision: `--depth N` caps import-graph traversal, defaulting to 2 (test →
intermediary → changed file). Depth 1 uses repoindex's resolver-quality
`import` rows; deeper hops walk the index's `imports` table.
Consequences: predictable scope growth; deep-dependency changes need an
explicit higher depth — or one `testmap record` run, whose exact rows are
not depth-limited.

## ADR-005: Lookup path reads only the index — no source parsing — Accepted

Context: the original plan ("parse test files, tree-sitter or
language-native AST") predates the suite invariant that relationship tools
query `.repoindex/index.db` rather than re-parsing source, and the
tree-sitter dependency was already rejected by xread (ADR-004), repomap
(ADR-004), and repoindex (ADR-007).
Decision: convention and direct-import links come from the `tests` table
repoindex already seeds; transitive links are a reverse BFS over the
`imports` table, resolving module strings by file stem within a language
family (same approach as rq findcycles); coverage rows are read as-is.
The only subprocesses are `git` (change detection) and the `repoindex
update` freshness guard.
Consequences: mapping quality is repoindex's to improve (data gaps are
repoindex bugs, as with rq); stem-matched transitive edges are heuristic
by nature, which ADR-003 already prices in; startup stays on the
stdlib-only fast path.

## ADR-006: A changed test file selects itself — Accepted

Context: editing `test_foo.py` means `test_foo.py` must run, but no
mapping layer targets test files.
Decision: any changed file that matches the suite's test-file naming
patterns is emitted as its own target, tagged `changed-test`, and joins
the run command.
Consequences: the everyday "I edited a test" case works without a special
flag; the tag keeps the reason visible like every other layer.

## ADR-007: record supports pytest only, via coverage.py contexts — Accepted

Context: per-test-file attribution needs per-test coverage contexts;
coverage.py's `dynamic_context = test_function` provides them in one
suite run, while go's coverprofile is per-package and c8's context story
is immature — each would need its own recorder.
Decision: `testmap record -- pytest [ARGS]` reruns the command as
`coverage run -m pytest` with a generated rcfile (dynamic contexts,
relative files), maps each context back to a test file, and writes
file→file rows. Contexts that cannot be attributed unambiguously are
skipped, not guessed. A run replaces prior coverage rows only for the
test files it saw, so partial-suite recordings never wipe other rows.
Other frameworks exit with a clear error; go/js recorders stay on the
roadmap.
Consequences: the most valuable layer ships without three bespoke
recorders; JS/Go projects still get convention + import layers.
