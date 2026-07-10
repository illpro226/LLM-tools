# repomap Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Python + tree-sitter for extraction — Superseded by ADR-004

Context: the suite prefers Python or Go; symbol outlines need real parsing
across five-plus languages.
Decision: Python with tree-sitter grammars, loaded lazily per language; regex
fallback for unsupported languages.
Consequences: shared grammar approach with `xread`/`repoindex`; startup cost
controlled by lazy loading; fallback quality is best-effort by design.

## ADR-002: Standalone-first ranking — Accepted (2026-07-07), amended by ADR-005

Context: ranking wants reference counts, which `.repoindex/index.db` has — but
repomap is an orientation tool and must work on repos with no index.
Decision: built-in lightweight import/occurrence counter as the default;
prefer the shared index when present.
Consequences: two ranking paths to test; repomap never requires `repoindex`.
(As built, only the built-in counter exists — see ADR-005.)

## ADR-003: Degradation order for --max-tokens — Accepted (2026-07-07)

Context: budget cuts must not truncate mid-thought (suite convention).
Decision: re-render at decreasing detail: drop low-rank files → drop
signatures → tree-only. Token estimate is bytes/4.
Consequences: renderer must be cheap enough to run multiple times per
invocation; output at any budget is structurally complete.
As built: before any outline is sacrificed, deep tree levels collapse so the
tree consumes at most half the budget (a huge tree must not starve the
outlines); at full detail at least 5 outlines are kept before switching to
the names-only level; the file-count search is a binary search over rank
order, so cost is O(log n) renders.

## ADR-004: Stdlib parsers instead of tree-sitter — Accepted (2026-07-07)

Context: ADR-001 planned tree-sitter, but the suite invariants demand
<100 ms startup and minimal dependencies, and xread hit the same fork and
chose stdlib (tools/xread/DECISIONS.md ADR-004). repomap needs only
top-level declarations — a much weaker requirement than xread's exact body
spans.
Decision: Python via stdlib `ast` (exact signatures and docstrings); JS/TS
and C/C++ via depth-tracking line scanners that strip strings/comments and
recognize declarations at brace depth 0; Go and Rust via column-0
declaration patterns (idiomatic formatting puts all top-level declarations
at column 0); every other language via one generic declaration regex.
Consequences: zero dependencies and fast startup; non-Python outlines are
heuristic (misses: indented module-nested items, multi-line declaration
heads) — acceptable for an orientation view, fixtures pin the behavior. If
tree-sitter is ever justified it slots in as an alternate extractor behind
`extractor_for` without changing the symbol model.

## ADR-005: Index-backed ranking deferred until repoindex pins its schema — Accepted (2026-07-07)

Context: ADR-002 wants `.repoindex/index.db` preferred as the ranking
source, but repoindex is Wave 3 and its seven-table schema exists only as
prose (tools/repoindex/DECISIONS.md ADR-001, Proposed). Implementing
against an invented schema would either pin repoindex's public interface
from the outside or silently break when the real schema lands.
Decision: ship with the built-in identifier-occurrence counter only. The
`rank()` function is the seam: when repoindex lands, index-backed scoring
replaces the counter body and the counter remains the no-index fallback.
Consequences: one ranking path today, two to test later; repomap places no
requirements on repoindex's schema; TESTING.md's index-preference area is
deferred with this ADR as the pointer.
