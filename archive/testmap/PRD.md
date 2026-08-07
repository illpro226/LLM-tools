# testmap PRD

## Problem statement

After a change, agents either run the entire test suite (slow, and `runlite` still has to distill 1,200 results) or guess at which tests matter. `testmap` maps changed files to the minimal set of tests that exercise them, so the agent runs 12 tests instead of 1,200. It pairs with `runlite`: scope first, distill second.

## Target users

- Coding agents choosing what to run after editing files.
- Humans and CI wrappers wanting a quick "which tests cover this change" answer.

## Scope

### Inputs

- Default changed-file set: `git diff --name-only HEAD` plus untracked files; an explicit file list may be passed instead.

### Mapping layers (applied in order)

1. **Naming conventions** — `foo.py` → `test_foo.py`, `foo.ts` → `foo.test.ts` / `foo.spec.ts`, and equivalents per language.
2. **Static import analysis** — parse test files (tree-sitter or language-native AST) and match their imports against changed modules, transitively up to `--depth N` (default 2).
3. **Recorded coverage (optional)** — `testmap record -- pytest` runs the suite under coverage and writes file→test rows into the shared `.repoindex/index.db` `tests` table with `source=coverage`, enabling exact lookups later.

### Output

- The test file/node list, one per line.
- A ready-to-run command for the detected framework (`pytest a b`, `npx vitest run a b`, `go test ./pkg/...`).
- Languages: Python, JS/TS, Go first.

## Non-goals

- Running the tests or summarizing their output (that is `runlite`).
- Guaranteeing completeness — the mapping is best-effort; callers can always fall back to the full suite.
- Building its own index; coverage rows go into `repoindex`'s shared database.

## Acceptance criteria

- On a fixture repo with known import relationships, convention matches and import-derived matches are both found; depth-2 transitive imports resolve, and `--depth 1` excludes them.
- `record` populates the `tests` table with `source=coverage`, and subsequent lookups prefer those exact rows.
- Output includes a correct runnable command for each detected framework.
- Changed-file detection covers modified and untracked files.
- Ordering is deterministic; results carry paths usable directly by the test runner.
