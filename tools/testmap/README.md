# testmap

`testmap` maps changed files to the tests that likely cover them, so an
agent runs 12 tests instead of 1,200. It pairs with `runlite`: scope first,
distill second. Lookups read the shared `.repoindex/index.db` — testmap
never parses source. See [`START.md`](/opt/des_stack/LLM-tools/START.md)
and [`PRD.md`](PRD.md).

```
testmap [FILES...]         # map changed files (default: git diff --name-only
                           #   HEAD + untracked) to covering tests
testmap record -- pytest [ARGS]   # run the suite under coverage.py and write
                           #   exact file->test rows into the shared index
```

Output: one target per line, tagged with the layer that selected it —
`(coverage)` (recorded fact, most trusted), `(changed-test)` (a changed
test file selects itself), `(convention)` (name pair like `foo.py` /
`test_foo.py`), `(import depth N)` (the test imports the changed module,
N hops through the import graph) — followed by a ready-to-run command per
detected framework (`pytest a b`, `npx vitest run a b`, `go test ./pkg`).
When a pair is found by several layers, the most-trusted tag wins. The
mapped set is best-effort, never a completeness claim: when nothing maps,
the full-suite command is printed as the fallback, and indexed changed
files with no mapped tests are noted individually.

Flags: `--depth N` (max transitive import depth, default 2), `--root DIR`,
`--json`, `--max-tokens N` (the target list collapses to a `(+N more)`
count; run commands are never dropped), `--no-update` (skip the automatic
`repoindex update`), `--repoindex CMD` (freshness-guard binary; also
`TESTMAP_REPOINDEX`; defaults to PATH, then the sibling
`tools/repoindex/repoindex.py`).

`record` currently supports pytest only (needs `coverage.py`); it replaces
prior coverage rows for the test files seen in the run and passes the test
command's exit code through. Exit codes: 0 mapped (possibly to nothing),
1 changed files undeterminable (not a git work tree and no explicit list),
2 no index / record prerequisites missing.
