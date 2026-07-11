# repoindex Status

Implemented (v0.1.4) and passing tests.

- `repoindex/` — importable package: `extract.py` (pure, filesystem-free
  `extract(path, source, lang=None) -> ExtractedFile`, ADR-006), `resolve.py`
  (repo-wide reference resolution, test-relationship seeding, Go structural
  `implements`), `db.py` (SQLite schema/writer/reconstruction), `walk.py`
  (repo file discovery + `.gitignore` housekeeping), `cli.py` (`build`,
  `update`, `status`, `sql`). `repoindex.py` at the tool root is the thin
  entry point (`python repoindex.py build`).
- Stdlib parsers only, no tree-sitter (ADR-007, matching xread/repomap/
  gitbrief's precedent): Python via `ast` (exact spans, deterministic
  qualnames `path::Class.method`); JS/TS and Go via brace/column-0 line
  scanners adapted from xread/repomap.
- Schema: `files`, `symbols`, `refs` (call/read/write/type-use,
  confidence resolved/heuristic — ADR-003), `imports`, `inherits`,
  `implements` (JS/TS `implements` keyword and Python ABC-derived bases are
  `confidence=resolved`; Go's structural, method-set-only satisfaction check
  is always `confidence=heuristic`), `tests` (source: convention/import
  seeded here; testmap writes `source=coverage` rows into the same table,
  and `update` preserves them when rebuilding derived rows), plus an
  internal `go_iface_methods` table so Go interfaces survive incremental
  updates without full re-parses.
- Resolution: imports + same-file/same-package name matching, with a
  repo-wide basename fallback for Python cross-directory imports that don't
  resolve directory-relatively. Unresolved/dynamic/ambiguous refs are kept
  with `confidence=heuristic`, never dropped.
- `update` re-extracts only changed files (mtime, then content-hash
  short-circuit); unchanged files are reconstructed from the DB (not
  re-parsed) to feed the repo-wide resolve/test-seed/Go-implements passes;
  everything commits in one transaction.
- `sql` is read-only (`mode=ro` + a write-statement pre-check); `status`
  reports freshness and per-language file/symbol counts.
- Tests: `tests/test_repoindex.py` (56 tests) against a shared fixture repo
  (`tests/fixtures/repo/`) covering every relationship kind — a call cycle,
  an import cycle (`py/cyc_a.py` <-> `py/cyc_b.py`, added for `rq findcycles`),
  a dynamic/getattr call, an ambiguous bare name, reads/writes, a resolvable
  type-use, a 3-deep inheritance chain, an ABC/interface implementation, a
  Go structural implementation, import- and convention-linked tests, and a
  dead symbol — plus incremental-update (parse-spy, hash short-circuit,
  one-transaction), `.gitignore` housekeeping, and determinism.

Not done / later: Rust/C++ extractors (Later milestone per ROADMAP.md);
JS/TS and Go call refs never see through a receiver (`obj.method()` is
always heuristic — no type inference); inherits/implements store the raw
parent/interface name rather than a resolved qualname; JS/TS template
literals spanning multiple lines aren't state-tracked (their inner braces
can skew depth, same limitation as xread/repomap); a dotted whole-module
import (`import a.b`) still resolves only with an alias; Python ABCs
imported from another file register as `inherits`, not `implements`
(abstractness is only detected same-file); bare-name decorators
(`@register` without a call) produce no ref.
