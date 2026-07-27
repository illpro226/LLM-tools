# repoindex Changelog

- 2026-07-27: stdout pinned to UTF-8 so non-ASCII paths and `sql` rows
  survive a cp1252 console (suite-wide fix).
- 2026-07-06: Added initial documentation scaffold.
- 2026-07-11: v0.1.5 — test seeding now links a test that imports a
  package to the package's `__init__.py` and to the modules it names
  (`from pkg import mod` -> `pkg/mod.py`); previously only `pkg.py` was
  tried, so real packages produced no link at all and every consumer of
  the `tests` table (codediff risk flags, testmap, `rq untested`)
  reported false "untested" results (fixes known-issue
  `repoindex-package-module-tests-not-linked`). Function-level imports
  are still invisible to the extractor — a module imported only inside a
  test function stays unlinked. 57 tests.
- 2026-07-10: v0.1.4 — the JS/TS and Go extractors now track function-local
  bindings the way the Python one has since v0.1.2: calls through names
  bound in the enclosing function (params, receiver, `const`/`let`/`var`,
  `:=`/`var`, nested function declarations, catch/func-literal bindings)
  become `<dynamic>` instead of resolving to an unrelated repo-wide symbol
  of the same name. JS/TS also opens a shadow region for anonymous
  callbacks (`describe('x', () => {`). Binding collection is deliberately
  over-approximated — a downgraded ref stays `heuristic`; it can never
  create a false `resolved` (closes known-issue
  `repoindex-local-var-shadowing-resolved-ref` for all three languages).
  56 tests.
- 2026-07-10: v0.1.3 — `update` no longer wipes `testmap record`'s
  `source=coverage` rows when rebuilding derived tables: coverage links are
  recorded facts, not re-derivable from source, so they now persist until
  their test file changes or either endpoint file leaves the repo (built
  for testmap v0.1.0; see its ADR-002). 48 tests.
- 2026-07-09: Adopted stdlib-only extraction (ADR-007), matching xread/
  repomap/gitbrief's precedent, instead of the originally planned
  tree-sitter. Implemented `build`/`update`/`status`/`sql`, the
  `repoindex.extract` library, repo-wide reference resolution, test-link
  seeding, and Go structural `implements` detection. v0.1.0.
- 2026-07-10: v0.1.2 — Python calls through names bound in the enclosing
  function (local assignments, parameters, nested defs, `except`/`nonlocal`
  bindings) are now recorded as `<dynamic>` instead of resolving to an
  unrelated repo-wide symbol of the same name, and local assignments no
  longer produce read/write refs to a shadowed module-level variable (fixes
  known-issue `repoindex-local-var-shadowing-resolved-ref`; the JS/TS and Go
  heuristic extractors don't track locals, so the same class of phantom ref
  remains possible there). 46 tests.
- 2026-07-09: Review fixes (v0.1.1): JS/TS braces inside comment/string-only
  lines no longer corrupt the depth counter (previously hid every top-level
  symbol after the first commented brace); Python import-time code (module
  and class bodies, class decorators) now produces call/read refs, so
  module-level-only callees no longer look dead; Python whole-module imports
  (`import lib; lib.add()`) now resolve instead of staying heuristic.
