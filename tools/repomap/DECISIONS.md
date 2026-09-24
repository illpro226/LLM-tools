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

## ADR-006: `--focus` narrows the output, it does not merely rank — Accepted (2026-07-27)

Context: dogfooding `repomap . --focus toch/cli.py` to plan an edit to one
465-line file returned ~180 lines — the focused file's outline first, then
every other ranked file's full symbol table, including ~90 individual test
functions (docs/known-issues/repomap-focus-does-not-narrow-output.md).
Reading the `def` lines out of the target file directly would have cost less,
inverting the suite's whole value proposition on precisely the "orient me on
one file" question repomap is the recommended answer for.
Decision: `--focus PATH` collapses every file outside the focus to its header
line plus a symbol count (`path [refs N] (12 symbols)`), with a note naming
the focus and how to get the outlines back. The flag name is kept: narrowing
is what "focus" reads as, and the previous behavior — rank-only — was the
mismatch. Independently, a run of three or more consecutive `test_*` functions
in any file collapses to one counted line, since a suite's test names are the
bulkiest and least informative thing an outline can carry.
Consequences: `--focus` no longer surfaces a neighbour's symbol by accident;
callers/callees of the focused file are named (with ref counts) but not
expanded, which the known issue accepted as sufficient. Dropping `--focus`
restores the full map, so nothing is unreachable. No `--only` or `--rank-by`
flag was added — one flag with the expected meaning beats two.

## ADR-007: `--max-tokens` defaults to 3000 — Accepted (2026-07-31)

Orientation is read at the *start* of a task, when the context window is
most valuable — the worst moment to spend 15,000 tokens unasked, which is
what `repomap .` cost on this repo before the default. It now costs ~2,900.

3000 is higher than the suite norm because a whole-repo map legitimately
needs more room than an excerpt: the measured 95th percentile is ~3185, and
a tighter cap would reshape ordinary calls rather than just clipping the
tail. `--max-tokens 0` restores unbounded output.

Suite-wide rationale and the measured evidence are in
`docs/decisions/0005-budgets-on-by-default.md`: across 661 logged calls in
the first 18 days of use, 1.4%% passed `--max-tokens`, while 3%% of calls
produced 8%% of all output. An opt-in cap protects only the caller who
already suspected the output would be large — the one who did not need
protecting.

## ADR-008: The tree rung caps entries per directory — Accepted (2026-09-24)

Context: ADR-003's last rung is tree-only, and its tree shrinks by
collapsing depth. Depth never shrinks a directory's *own* listing, so a
root holding 3,000 files printed ~12,800 tokens against the 3,000 default:
the ladder ended in a rung that was still O(files) (INVARIANTS.md).
Decision: past depth 1, the tree lists at most N entries per directory
(dirs and files each), the rest counted as `… (+K more files)`; N is the
largest that fits, found by binary search, and the output names
`--max-tokens`. The half-budget reservation for outlines uses the same
fit, and is skipped when there are no outlines to reserve it for.
Consequences: every budget now terminates, flooring at depth 1 with one
entry of each kind — constant in the file count.

