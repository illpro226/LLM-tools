# repoindex Architecture

Status: implemented (v0.1.0). This describes the as-built design.

## Overview

`repoindex` is the suite's foundation: a stdlib-parser extraction library (ADR-007
— no tree-sitter, matching the precedent `xread`/`repomap`/`gitbrief` already set)
plus an incremental SQLite writer. The CLI is thin; the two real products are the
schema (what `callgraph`, `rq`, `testmap`, and `codediff` query) and the importable
`repoindex.extract` library (what `codediff` reuses for before/after parsing).

```
repoindex.extract (library)
  extractor per language ──► ExtractedFile{symbols, refs, imports,
                                           inherits, implements, tests}
repoindex (CLI)
  build   ──► full walk → extract → write
  update  ──► changed files only (mtime/hash), one transaction
  status  ──► freshness + per-language counts
  sql     ──► read-only escape hatch, column-aligned
```

## Schema

One SQLite file at `.repoindex/index.db`; joins across relationship tables are
the point.

| table | contents |
|---|---|
| `files` | path, language, mtime, content hash |
| `symbols` | qualified name, kind, file, line span, visibility/exported |
| `refs` | from-location → to-symbol, kind (`call`/`read`/`write`/`type-use`), confidence (`resolved`/`heuristic`) |
| `imports` | file → module/symbol, alias, line |
| `inherits` | child → parent symbol (raw name, as declared) |
| `implements` | symbol → interface/protocol symbol (raw name), plus a `confidence` column: `resolved` for an explicit keyword (JS/TS `implements`, Python ABC-derived bases), `heuristic` for Go's structural (method-set-only) satisfaction check, since Go has no `implements` keyword |
| `tests` | test → covered file/symbol, source (`convention`/`import`/`coverage`) |

Indexes on `symbols.qualname`, `refs.to_symbol`, and `files.path` cover the
downstream tools' hot queries. An internal `go_iface_methods` table (file,
interface, method) persists each Go interface's method-name set so an
`update` that skips re-parsing an unchanged Go file can still recompute
`implements` edges without losing that data.

## The `repoindex.extract` contract

Pinned before any dependent tool is built (see ADR-006). `codediff` parses
*before* versions that exist only as git blobs, so the library must never
assume the filesystem:

- `extract(path, source) -> ExtractedFile` is **pure**: `source` (str/bytes)
  is the content to parse; `path` is a label and language hint only. No
  filesystem, git, or database access inside extraction. The before side of a
  diff is `extract(path, git_show(ref, path))` — same machinery, no special
  case.
- `detect_language(path, source=None) -> lang | None` is a separate,
  caller-overridable step; `extract` takes an explicit `lang=` override.
- `ExtractedFile` is a plain dataclass (symbols, raw refs, imports, inherits,
  implements, test hints) with no SQLite types or connection — the DB writer
  consumes it, but so does codediff's in-memory before/after comparison.
- `symbols[].qualname` is the stable join key for matching a symbol across
  two versions of a file; qualname construction and list ordering must be
  deterministic for identical input.
- Refs in `ExtractedFile` are **raw names, unresolved**. Resolution against
  imports/scope is a separate repo-wide pass that only the indexer runs;
  single-file consumers get useful output without it.

## Components

- **Extractor interface** — one module per language (Python, JS/TS, Go first)
  implementing the contract above. Adding a language is one file; the
  interface is the contract. Python via stdlib `ast` (exact spans); JS/TS via
  a brace-tracking line scanner adapted from `xread`; Go via a column-0
  declaration scanner adapted from `repomap` (ADR-007).
- **Reference resolver** — two passes: extract raw names, then resolve against
  the import table plus scope-aware name matching. Unresolvable/dynamic edges
  are stored with `confidence=heuristic`, never dropped — downstream tools
  decide how to present uncertainty.
- **Test-relationship seeding** — convention (name patterns) and import-derived
  test→target rows, tagged by `source`; `testmap record` later adds
  `source=coverage` rows through the same table.
- **Incremental updater** — compares mtime, then content hash, re-extracts only
  changed files, deletes-and-reinserts their rows inside one transaction.
  Fast enough that every downstream tool runs `repoindex update` implicitly.
- **SQL escape hatch** — `repoindex sql "SELECT ..."` opens the database
  read-only and column-aligns output; writes are rejected.
- **Housekeeping** — ensures `.repoindex/` is present in `.gitignore`.

## Key decisions

- Language: Python; stdlib `sqlite3`; stdlib-only parsing, no tree-sitter
  (ADR-007) — exact `ast` spans for Python, heuristic scanners for JS/TS/Go.
- Store uncertainty rather than hiding it (the confidence column) — accuracy
  claims live in the data, not the docs. The stdlib-only choice pushes more
  edges into `confidence=heuristic` than tree-sitter would have; that's the
  explicit tradeoff ADR-007 accepts.
- Library-first: the CLI is a wrapper over `repoindex.extract` + a writer, so
  other tools never re-implement parsing.

## Dependencies

Stdlib only — no tree-sitter, no grammar packages (ADR-007).
