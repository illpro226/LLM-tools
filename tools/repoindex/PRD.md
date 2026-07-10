# repoindex PRD

## Problem statement

Every relationship-aware tool (callers, impact, test mapping, semantic diff) needs symbol and reference data, and without a shared foundation each tool would re-parse the repo independently. `repoindex` maintains one incremental, stdlib-parser-built SQLite database at `.repoindex/index.db` holding symbols and every cheap-to-extract relationship. Parse the repo once; `callgraph`, `codediff`, `testmap`, `repomap`, and `rq` become SQL queries over the same index.

## Target users

- The other tools in this suite (`callgraph`, `rq`, `codediff`, `testmap`, `repomap`) as their query backend.
- Agents and humans running ad-hoc queries via the SQL escape hatch.

## Scope

### CLI surface

- `repoindex build` — full index.
- `repoindex update` — incremental: re-extract only files whose mtime/hash changed, in one transaction; fast enough to run implicitly before every query.
- `repoindex status` — freshness, per-language file/symbol counts.
- `repoindex sql "SELECT ..."` — read-only raw query escape hatch with column-aligned output.

### Schema (one SQLite file — joins across relationships are the point)

| table | contents |
|---|---|
| `files` | path, language, mtime, content hash |
| `symbols` | qualified name, kind (func/class/method/const/type), file, line span, visibility/exported |
| `refs` | from-location → to-symbol, kind (`call`, `read`, `write`, `type-use`), confidence (`resolved`/`heuristic`) |
| `imports` | file → module/symbol, alias, line |
| `inherits` | child symbol → parent symbol |
| `implements` | symbol → interface/protocol symbol |
| `tests` | test symbol/file → covered file/symbol, source (`convention`, `import`, `coverage`) |

### Extraction

- Stdlib parsers only (ADR-007), matching the precedent set by `xread`/`repomap`/`gitbrief`: Python via `ast` (exact spans), JS/TS and Go via heuristic line/brace scanners. Python, JS/TS, Go first. The extractor interface is designed so adding a language is one file.
- Resolve references via imports plus scope-aware name matching; store unresolved/dynamic edges with `confidence=heuristic` rather than dropping them.
- The `tests` table carries a `source` column so `testmap` can add coverage-recorded rows later.
- Extraction logic ships as an importable library (`repoindex.extract`) so `codediff` can parse before/after file versions with the same machinery.

### Housekeeping

- `.repoindex/` is added to a generated `.gitignore` entry; the index is never committed.

## Non-goals

- Answering user-facing questions itself (that is `callgraph` and `rq`); `repoindex` builds and serves the data.
- Full type inference or IDE-grade resolution; heuristic edges are stored and labeled, not perfected.
- Indexing vendored/generated directories.

## Acceptance criteria

- On the fixture repo, every table contains the expected rows (verified per table in tests).
- Incremental update: touching one file re-extracts only that file — a test proves an untouched file is not re-parsed — and runs inside one transaction.
- Unresolved/dynamic references appear with `confidence=heuristic` instead of being dropped.
- `status` reports freshness and per-language counts; `sql` rejects writes and column-aligns results.
- `repoindex.extract` is importable and parses a standalone file version (the `codediff` use case).
- `.gitignore` handling keeps `.repoindex/` untracked.
