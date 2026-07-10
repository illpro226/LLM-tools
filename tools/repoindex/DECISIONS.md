# repoindex Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: One SQLite file as the suite-wide contract — Accepted (2026-07-09)

Context: five tools need symbol/relationship data; per-tool stores would
fragment truth and multiply parsing cost.
Decision: a single `.repoindex/index.db` with the seven-table schema from the
PRD; joins across relationship tables are the design center. The schema is a
public interface for `callgraph`, `rq`, `testmap`, and `codediff`.
Consequences: schema changes are suite-wide breaking changes and need
migration notes; stdlib sqlite3 suffices everywhere.

## ADR-002: Library-first — the CLI wraps repoindex.extract — Accepted (2026-07-09)

Context: `codediff` must parse before/after file versions with identical
machinery; a CLI-only tool would force it to fork the parser.
Decision: extraction ships as an importable library
(`extract(path, source) -> ExtractedFile`); the CLI is a walker + writer over
it. One extractor module per language is the add-a-language contract.
Consequences: the library surface is versioned and tested independently of
the database.

## ADR-003: Store uncertainty instead of dropping it — Accepted (2026-07-09)

Context: static resolution can't decide dynamic/duck-typed references;
silently dropping them makes downstream graphs falsely confident.
Decision: unresolved edges persist with `confidence=heuristic`; resolved ones
with `confidence=resolved`. Presentation is downstream's job.
Consequences: consumers must handle both confidence values; accuracy claims
live in the data.

## ADR-004: Incremental update cheap enough to be implicit — Accepted (2026-07-09)

Context: downstream tools auto-run `repoindex update` before every query;
if that's slow, they'll skip it and go stale.
Decision: change detection by mtime then content hash; only changed files
re-extracted, delete+reinsert per file inside one transaction.
Consequences: update cost scales with change size, not repo size; the
no-reparse-of-untouched-files property is test-enforced.

## ADR-005: tests table carries a source column — Accepted (2026-07-09)

Context: test→target rows come from three generations of evidence
(convention, import, coverage) with different trust levels, written by two
tools (repoindex seeds, testmap records).
Decision: every row is tagged `convention` / `import` / `coverage`.
Consequences: consumers can rank evidence; testmap writes through the same
table without schema changes.

## ADR-006: extract() is pure and filesystem-free — Accepted (2026-07-09)

Context: `codediff` must parse *before* file versions that exist only as git
blobs, never on disk. If `extract` reads files, stats mtimes, or touches the
DB, codediff forces a refactor of the library after dependents already use it.
Decision: `extract(path, source)` takes content as an argument and is pure;
language detection is a separate overridable step; `ExtractedFile` is a plain
dataclass with raw (unresolved) refs; import/scope resolution is a distinct
repo-wide pass run only by the indexer. Full contract in ARCHITECTURE.md.
Consequences: the CLI walker owns all I/O (read, hash, mtime); extraction is
trivially testable on string fixtures; deterministic qualnames become a
tested guarantee since they're the before/after join key.

## ADR-007: Stdlib parsers instead of tree-sitter — Accepted (2026-07-09)

Context: the PRD/ARCHITECTURE originally specified tree-sitter for all
parsing, but `xread`, `repomap`, and `gitbrief` each independently deviated
from the same planned design to stdlib-only parsers, citing the suite's
<100ms startup budget and minimal-dependencies convention (see e.g. xread
ADR-004). tree-sitter is not installed in the dev environment. Leaving
repoindex as the one tool still planning tree-sitter would mean the suite's
foundational tool carries the one heavy dependency none of its consumers do.
Decision: `repoindex.extract` uses stdlib parsers exclusively — Python via
`ast` (exact spans, deterministic qualnames); JS/TS via a brace-tracking line
scanner adapted from `xread`'s; Go via a column-0 declaration scanner adapted
from `repomap`'s. Same one-module-per-language extractor interface from
ADR-002/ADR-006 either way.
Consequences: zero new dependencies, consistent startup cost across the
suite. JS/TS/Go spans and reference resolution are heuristic rather than
grammar-exact, which pushes more edges into `confidence=heuristic` (ADR-003)
than tree-sitter would have — an explicit, labeled accuracy tradeoff, not a
silent one. If tree-sitter is ever justified, it slots in as an alternate
extractor backend per language without changing the schema or the
`extract(path, source) -> ExtractedFile` contract.
