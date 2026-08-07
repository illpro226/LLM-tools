# testmap Architecture

Status: implemented (single-file `testmap.py`, stdlib only).

## Overview

`testmap` layers mappers of increasing precision over one changed-file set,
unions their results keeping the most-trusted tag per pair (ADR-001), and
formats runnable commands. Everything the lookup path knows comes from the
shared `.repoindex/index.db` (ADR-005) — testmap parses no source.

```
changed files (git diff --name-only HEAD + untracked, or explicit args)
  ├─► coverage mapper     (tests table, source=coverage — recorded fact)
  ├─► changed-test self   (a changed test file selects itself, ADR-006)
  ├─► convention/import   (tests table rows repoindex already seeded)
  └─► transitive imports  (reverse BFS over the imports table, --depth N)
union, best tag per pair ──► target list + per-framework run command
```

## Components

- **Freshness guard** — runs `repoindex update` before every lookup
  (`--no-update` skips; binary via `--repoindex`, `TESTMAP_REPOINDEX`,
  PATH, or the sibling checkout), so answers never come from a stale index.
- **Change detector** — `git diff --name-only HEAD` plus
  `git ls-files --others --exclude-standard`; requires `--root` to be the
  work-tree top (git paths are toplevel-relative and must match index
  paths); explicit file arguments bypass git entirely.
- **Layer queries** — coverage/convention/import rows straight from the
  `tests` table; depth ≥ 2 walks a reverse import graph built from the
  `imports` table, resolving module strings by file stem within a language
  family, same-directory candidates first (mirrors rq findcycles). Test
  files are recognized by the same naming patterns repoindex's seeder uses;
  they are BFS leaves — only production files keep expanding.
- **Framework detector / command formatter** — python → `pytest`; js/ts →
  `npx vitest run` / `npx jest` sniffed from config files and package.json
  (a note when undetectable); go → `go test ./pkg` per package dir of the
  selected `_test.go` files. Run commands are emitted as notes, which the
  `--max-tokens` renderer never collapses.
- **Recorder** (`testmap record -- pytest`) — reruns the suite under
  `coverage run` with `dynamic_context = test_function`, attributes each
  context back to a test file (handles both dotted-module and pytest-cov
  `path::node` context shapes), and writes `source=coverage` rows into the
  shared table (ADR-007). repoindex's `update` preserves those rows.

## Key decisions

See DECISIONS.md: layered union tagged by source (001), shared storage in
repoindex's DB (002), best-effort scoping with full-suite fallback (003),
depth default 2 (004), index-only lookups — no tree-sitter, superseding
this file's original parse-the-test-files plan (005), changed-test self
mapping (006), pytest-only recorder (007).

## Dependencies

`git` at runtime for change detection; `coverage.py` only for `record`.
No tree-sitter, no third-party imports.
