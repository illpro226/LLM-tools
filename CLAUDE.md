# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

LLM-tools is a toolkit of small, composable CLI utilities that help coding agents (Claude Code, aider, etc.) spend fewer tokens per task. The unifying idea: never put raw, bulky content into an agent's context when a compressed, targeted view will do.

The suite is complete at 11 tools — `tokq`, `runlite`, `xread`, `sgrep` (Wave 1), `repomap`, `gitbrief`, `structo` (Wave 2), `repoindex`, `rq`, `testmap` (Wave 3), and `codediff` (Wave 4). The build list is closed (docs/decisions/0003): `factbook` and `docsnip` stay deferred indefinitely, revivable only on recorded dogfooding evidence. Their directories (plus `callgraph`, merged into `rq`) contain just the standard doc set (`README.md`, `PRD.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`, `DECISIONS.md`, `TESTING.md`, `CONTRIBUTING.md`) and a `.gitkeep`. Check a tool's `STATUS.md` first — it says outright whether the tool is "Scaffold only" or implemented.

- [`START.md`](START.md) — canonical description of every tool in the suite plus its bootstrap prompt. Read this before starting a new tool.
- [`INVARIANTS.md`](INVARIANTS.md) — rules that hold across every tool (output, semantics, performance, docs). A change that breaks one needs a decision record in `docs/decisions/`, not just a PR.
- [`docs/decisions/0001-starting-list-and-deferrals.md`](docs/decisions/0001-starting-list-and-deferrals.md) — original build plan and scope. Supersedes START.md's 14-tool list: `callgraph` merged into `rq`; `codediff`, `factbook`, `docsnip` deferred. Build order is Wave 1 (`tokq` done, `runlite`, `xread`, `sgrep`) → Wave 2 (`repomap`, `gitbrief`, `structo`) → Wave 3 (`repoindex`, `rq`, `testmap`).
- [`docs/decisions/0002-wave-4-codediff.md`](docs/decisions/0002-wave-4-codediff.md) — Wave 4 un-defers `codediff` alone (`factbook`/`docsnip` stay deferred) and amends its PRD: no tree-sitter (repoindex's pure `extract()` serves both diff sides) and no ordinal risk grade (flat explainable flags instead).
- [`docs/decisions/0003-close-the-list.md`](docs/decisions/0003-close-the-list.md) — closes the build list at 11 tools; no Wave 5. `factbook`'s job is covered by the AGENTS.md convention, `docsnip`'s by docs MCP channels plus `inspect`/`xread`; either revives only via a new decision record citing recorded known-issue evidence.
- `docs/README.md`, `docs/PRDs/README.md`, `docs/known-issues/README.md` — index pages; per-tool PRDs live at `tools/<name>/PRD.md`.
- `doc/` is a compatibility alias for `docs/` — put new documentation in `docs/`, not `doc/`.

Note: doc cross-links throughout the repo point at `/opt/des_stack/LLM-tools/...` (an earlier container checkout path), not the current location on disk. Treat them as repo-relative.

## Dogfood the suite while working here

When working in this repo, prefer the suite's own tools over built-ins for the
jobs they cover — real usage is the field test fixtures can't provide:

- `xread FILE --symbol NAME` instead of reading a whole file for one function;
  `--query`/`--headings` for docs.
- `repomap` for orientation after a compaction or when entering an unfamiliar
  part of the repo, instead of `ls` + reading CLAUDE.md sections.
- `repoindex` + `rq` (`whouses`, `impact`, `deadcode`, `untested`) for
  relationship questions, instead of grepping for call sites.
- `testmap [FILES]` after editing implementation files to pick the tests to
  run, instead of running a whole suite (needs git for auto-detection; pass
  files explicitly here until the repo is git-initialized).
- `tokq lint` on any doc you edit before finishing; `tokq dir` to see where
  the token weight lives.
- `structo` for any JSON/YAML/JSONL/XML you'd otherwise read raw.
- `runlite -- CMD` when wrapping a build/test command whose full log you don't
  need.
- `gitbrief` (`hunks`, `log`, `pr BASE`) for layered views of the working
  diff and history, instead of raw `git diff`/`git log`.
- `codediff` (default worktree vs HEAD; `--staged`, `REF`, `A..B`) for what
  a change *means* — API/behavior/removed/mechanical plus risk flags —
  before committing or when reviewing, instead of re-reading hunks.

- `sgrep` for token-budgeted content search (`--files-only`/`--counts-only`
  first, then narrow), instead of raw grep dumps.

Two rules make this useful rather than ritual: (1) whenever a built-in was
genuinely easier or a tool's output missed what you needed, file it in
`docs/known-issues/` (one file per issue) — that friction is the product
feedback this section exists to collect; (2) when a new tool reaches
implemented status, add it to the list above.

## Suite-wide conventions (apply to every tool)

- One directory per tool: `tools/<name>/`, each a standalone CLI installable on PATH.
- Plain-text, deterministic output meant to be read by an LLM: compact, stable ordering, no ANSI color, no spinners, no timestamps in normal output.
- Every line that makes a claim about code carries a `path:line` reference so a finding can be followed up with `xread`.
- Every tool whose output can grow supports `--max-tokens N` (or `--max-bytes`), degrading by summarizing harder — never by truncating mid-thought.
- Prefer Python or Go, minimal dependencies, fast startup (~100ms budget on the no-heavy-deps path).
- Offline and deterministic by default: any LLM call is opt-in behind an explicit flag and never receives raw source/diffs, only the tool's own compact structured summary.
- Confidence is two-valued (`resolved` | `heuristic`), never an ordinal HIGH/MEDIUM/LOW scale — static analysis can't honestly support finer grades.
- Relationship-shaped tools (`rq`, `testmap` lookups) query the shared `.repoindex/index.db` rather than re-parsing source; excerpt/orientation tools (`xread`, `sgrep`, `repomap`) parse directly and must keep working when no index exists.

## Working in a tool directory

There's no repo-wide build system; each tool is self-contained. For the implemented tools:

```
cd tools/tokq
python -m pytest        # run tests
./tokq.py FILE...        # meter files (chmod +x first, or `python tokq.py ...`)
./tokq.py dir PATH        # token-weighted directory tree
./tokq.py lint PATH...    # flag context-wasteful content; --budget N gates scripts

cd tools/runlite
python -m pytest        # run tests (canned-log fixtures, no toolchains needed)
./runlite.py -- CMD...    # run a command, print a failure-focused report

cd tools/xread
python -m pytest        # run tests
./xread.py FILE --symbol NAME | --lines A-B [--scope] | --query "..." | --headings

cd tools/sgrep
python -m pytest        # run tests (real-rg tests skip if rg is absent)
./sgrep.py PATTERN [PATH...] [--files-only|--counts-only]   # needs ripgrep

cd tools/repomap
python -m pytest        # run tests
./repomap.py [DIR] [--focus PATH] [--max-tokens N]   # tree + ranked symbol outlines

cd tools/gitbrief
python -m pytest        # run tests (builds temp repos; needs git on PATH)
./gitbrief.py [hunks [FILE...] | show FILE | log | pr BASE]   # layered git views

cd tools/structo
python -m pytest        # run tests (-m "not slow" skips the memory test)
./structo.py FILE [--path a.b[0].c] [--sample N]   # schema/shape of a data file

cd tools/repoindex
python -m pytest        # run tests (57 tests against tests/fixtures/repo/)
./repoindex.py build     # full index -> .repoindex/index.db
./repoindex.py update    # incremental (mtime/hash change detection)
./repoindex.py status    # freshness + per-language file/symbol counts
./repoindex.py sql "SELECT ..."   # read-only escape hatch, column-aligned

cd tools/rq
python -m pytest        # run tests (41 tests; builds the repoindex fixture index)
./rq.py whouses SYMBOL | implements IFACE | inherits BASE | impact SYMBOL [--depth N]
./rq.py publicapi [PATH] | deadcode [--include-exported] | findcycles | untested
#   shared flags (--root, --json, --max-tokens, --no-update) work before or after the subcommand

cd tools/testmap
python -m pytest        # run tests (22 tests; record test needs coverage.py, else skips)
./testmap.py [FILES...] [--depth N]   # changed files -> covering tests + run command
./testmap.py record -- pytest [ARGS]  # record exact coverage into the shared index

cd tools/codediff
python -m pytest        # run tests (28 tests; scripted temp repos, needs git + sibling repoindex)
./codediff.py [REF|A..B] [--staged] [--json] [--max-tokens N]   # semantic diff summary
```

All are stdlib-only Python CLIs with tests in `tests/` against committed fixtures; every one except `repoindex` is a single file. `tokq` uses `tiktoken` (o200k_base) when installed and falls back to a bytes/3.7 heuristic otherwise, always stating which method was used. `runlite` passes through the wrapped command's exit code (its own failures use reserved codes 125/127) and picks an output extractor by command name, then log fingerprint, then a generic fallback. `xread` parses Python via stdlib `ast`, JS/TS via a brace-tracking heuristic, and markdown headings as a symbol kind (its DECISIONS.md ADR-004 records why tree-sitter was dropped). `sgrep` requires the `rg` binary at runtime (PATH, `--rg`, or `SGREP_RG` — ripgrep 15.1.0 is installed via winget and resolves on PATH here). `repomap` extracts top-level symbols with stdlib parsers (Python `ast`; heuristic scanners for JS/TS, Go, Rust, C/C++; generic regex fallback — its ADR-004), ranks files by identifier reference counts (index-backed ranking deferred until `repoindex` pins its schema — its ADR-005), and degrades under `--max-tokens` by collapsing deep tree levels, then dropping low-rank outlines, then signatures, then going tree-only. `gitbrief` is read-only subprocess git plumbing (`--no-optional-locks`, porcelain formats, renames off); its `pr` changed-symbol list uses stdlib extraction of before/after blobs for Python/JS-TS (its ADR-005 supersedes the optional-tree-sitter plan). `structo` streams every input (incremental JSON tokenizer, per-line JSONL, PyYAML events — its one optional dependency, iterparse XML) with memory O(schema+samples) test-enforced; sampled figures carry a `~` marker. `repoindex` is a package (`repoindex/extract.py`, `resolve.py`, `db.py`, `walk.py`, `cli.py`, plus the `repoindex.py` entry point): stdlib parsers only, no tree-sitter (its ADR-007, following the same precedent as xread/repomap/gitbrief above); `extract()` is pure and filesystem-free so `codediff` can later reuse it on git-blob content; a repo-wide pass resolves refs/tests against imports and scope, tagging each `confidence=resolved` or `heuristic` rather than dropping what it can't resolve; `update` re-extracts only changed files (mtime, then hash) and reconstructs unchanged ones from the DB so the repo-wide passes still see everything, all inside one transaction. `rq` is a thin query pack over that index and never parses source (its ADR-002 — data gaps are repoindex bugs): it runs `repoindex update` before every query (skippable with `--no-update`; finds the binary via `--repoindex`/`RQ_REPOINDEX`/PATH/the sibling checkout), matches symbol names case-sensitively via `substr()` suffixes (SQLite `LIKE` is case-insensitive), answers `impact` with a per-level SQL BFS because the innermost-enclosing-symbol join can't live in a recursive CTE (its ADR-003), keeps `deadcode` conservative by default (exported/dunder/test-file/heuristically-referenced symbols excluded; a caveat counts heuristic refs that could hide callers — its ADR-004), collapses output under `--max-tokens` to per-group `(+N more)` counts (its ADR-005), and prints `publicapi` without signatures because the index stores none (its ADR-006). Exit codes: 1 symbol not found, 2 no index. `testmap` maps changed files (git diff + untracked, `--root` must be the work-tree top, or an explicit list) to covering tests as a union of layers tagged by most-trusted source — recorded coverage, changed-test self-selection, then the convention/import rows repoindex seeded, then a reverse BFS over the `imports` table for `--depth ≥ 2` (default 2) — and like `rq` it never parses source and runs `repoindex update` first (its ADR-005; env `TESTMAP_REPOINDEX`); it emits one `test:1 covers target (tag)` line per pair plus a per-framework run command (`pytest`, `npx vitest run`/`npx jest` sniffed from configs, `go test ./pkg`) that `--max-tokens` never collapses, notes indexed changed files with no mapped tests, and prints the full-suite command when nothing maps (its ADR-003). `testmap record -- pytest [ARGS]` reruns the suite under coverage.py dynamic contexts and writes exact `source=coverage` rows into the shared `tests` table (pytest-only so far, its ADR-007; repoindex `update` preserves those rows), replacing prior coverage rows only for the test files seen. Exit codes: 1 changed files undeterminable, 2 no index; `record` passes the test command's exit code through. `codediff` diffs changed files at the symbol level by running `repoindex.extract` on both sides — git blob and worktree/index, the library reuse repoindex ADR-006 planned — and classifies into API (signatures as `old → new`, renames paired by exact normalized-body equality, not a fuzzy threshold — its ADR-004), Behavior (literal/default changes `3 → 5`, conditional and call deltas), Removed (deprecation markers noted), and Mechanical (formatting/comment-only via Python AST-dump equality, import reshuffles; one line per file); risk is a flat list of explainable flags (sensitive-path keywords and the behavior-delta threshold from `.codediff.toml`, public-API surface, stale or missing test coverage via the shared `tests` table after an implicit `repoindex update` — flags `--repoindex`/`--repoindex-lib`, env `CODEDIFF_REPOINDEX_BIN`/`CODEDIFF_REPOINDEX`), never a grade (docs/decisions/0002); there is no `--llm` flag — `--json` is the compact narrator payload (its ADR-005); `--max-tokens` collapses mechanical first, then behavior detail, then to per-section counts, and never drops the risk block. Exit codes: 0 ok, 2 usage/git error.

For any other tool, there is nothing to run yet — start from that tool's `PRD.md` and the corresponding bootstrap prompt in `START.md`, and follow the suite-wide conventions above plus `INVARIANTS.md`.

## Notes on repo state

- Git repository since 2026-07-10; remote: `github.com/illpro226/LLM-tools` (private). Commit style per `AGENTS.md`: short, imperative subjects (`add xread token cap tests`).
- `.claude/settings.local.json` contains an allowlist scoped to `tokq` development (pytest, tiktoken checks, venv setup) — it's specific to work already done there, not a general policy.
