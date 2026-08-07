# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

LLM-tools is a toolkit of small, composable CLI utilities that help coding agents (Claude Code, aider, etc.) spend fewer tokens per task. The unifying idea: never put raw, bulky content into an agent's context when a compressed, targeted view will do.

The suite is complete at 11 tools — `tokq`, `runlite`, `xread`, `sgrep` (Wave 1), `repomap`, `gitbrief`, `structo` (Wave 2), `repoindex`, `rq`, `testmap` (Wave 3), and `codediff` (Wave 4). Two of them, `rq` and `testmap`, are **retired from default use** (docs/decisions/0006): a month of logged usage produced 2 calls and 0 calls respectively, so they no longer appear in the guidance below. The code and tests stay; `repoindex` stays fully live as the library behind `codediff`. The build list is closed (docs/decisions/0003): `factbook` and `docsnip` stay deferred indefinitely, revivable only on recorded dogfooding evidence. Their directories (plus `callgraph`, merged into `rq`) contain just the standard doc set (`README.md`, `PRD.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `STATUS.md`, `ROADMAP.md`, `CHANGELOG.md`, `DECISIONS.md`, `TESTING.md`, `CONTRIBUTING.md`) and a `.gitkeep`. Check a tool's `STATUS.md` first — it says outright whether the tool is "Scaffold only" or implemented.

- [`START.md`](START.md) — canonical description of every tool in the suite plus its bootstrap prompt. Read this before starting a new tool.
- [`INVARIANTS.md`](INVARIANTS.md) — rules that hold across every tool (output, semantics, performance, docs). A change that breaks one needs a decision record in `docs/decisions/`, not just a PR.
- `docs/decisions/` — the binding record; read one before changing what it
  settled. 0001 build plan and deferrals (supersedes START.md's 14-tool
  list: `callgraph` merged into `rq`) · 0002 un-defers `codediff` · 0003
  closes the list at 11 tools, no Wave 5 · 0004 accepts an MCP stdio
  adapter for xread/sgrep/structo/gitbrief (planned in `mcp/`, not built)
  · 0005 token budgets on by default · 0006 retires `rq`/`testmap` from
  default use on logged-usage evidence · 0007 savings-log operations
  (no repeat-call memo; compact `events.jsonl` only past 4 MB / 50 ms).
- `docs/README.md`, `docs/PRDs/README.md`, `docs/known-issues/README.md` —
  index pages; per-tool PRDs live at `tools/<name>/PRD.md`.
- `doc/` is a compatibility alias for `docs/` — put new documentation in `docs/`, not `doc/`.

Note: doc cross-links throughout the repo point at `/opt/des_stack/LLM-tools/...` (an earlier container checkout path), not the current location on disk. Treat them as repo-relative.

## Dogfood the suite while working here

When working in this repo, prefer the suite's own tools over built-ins for the
jobs they cover — real usage is the field test fixtures can't provide:

- `xread FILE --symbol NAME` instead of reading a whole file for one function;
  `--query`/`--headings` for docs.
- `repomap` for orientation after a compaction or when entering an unfamiliar
  part of the repo, instead of `ls` + reading CLAUDE.md sections.
- `structo` for any JSON/YAML/JSONL/XML you'd otherwise read raw; when the
  question is about *values* across records rather than shape, `structo
  FILE --select f1,f2 | awk ...` instead of a throwaway analysis script.
- `runlite -- CMD` when wrapping a build/test command whose full log you don't
  need.
- `gitbrief` (`hunks`, `log`, `pr BASE`) for layered views of the working
  diff and history, instead of raw `git diff`/`git log`.
- `codediff` (default worktree vs HEAD; `--staged`, `REF`, `A..B`) for what
  a change *means* — API/behavior/removed/mechanical plus risk flags —
  before committing or when reviewing, instead of re-reading hunks.
- `sgrep` for token-budgeted content search (`--files-only`/`--counts-only`
  first, then narrow), instead of raw grep dumps. Add `--no-collapse` when
  you need every match rather than a representative per cluster — "edit
  each of these 40 sites" work.

**Situational, not default.** `tokq lint`/`tokq dir` when you're deciding
what to cut from a document or hunting where token weight lives — not as a
finishing ritual on every doc edit. (`rq` and `testmap` used to be listed
here too. Logged usage says the trigger never fires: `sgrep` settles
"who calls this?" cheaper, and these test suites run in seconds. Don't
reach for them; see docs/decisions/0006.)

Two rules make this useful rather than ritual: (1) whenever a built-in was
genuinely easier or a tool's output missed what you needed, file it in
`docs/known-issues/` (one file per issue) — that friction is the product
feedback this section exists to collect; (2) when a new tool reaches
implemented status, add it to the list above.

## Suite-wide conventions (apply to every tool)

- One directory per tool: `tools/<name>/`, each a standalone CLI installable on PATH.
- Plain-text, deterministic output meant to be read by an LLM: compact, stable ordering, no ANSI color, no spinners, no timestamps in normal output.
- Every line that makes a claim about code carries a `path:line` reference so a finding can be followed up with `xread`.
- Every tool whose output can grow supports `--max-tokens N` (or `--max-bytes`), degrading by summarizing harder — never by truncating mid-thought. The budget is **on by default** (docs/decisions/0005) with `--max-tokens 0` as the escape hatch; every rung of a ladder must be bounded, not merely smaller; and any degradation that removes what was asked for says so and names the flag. Modes that feed another program (`structo --select`/`--raw`, `--json` payloads) are exempt from the default, never from an explicit cap.
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
python -m pytest        # run tests (30 tests; builds temp repos, needs git on PATH)
./gitbrief.py [hunks [FILE...] | show FILE | log | pr BASE]   # layered git views

cd tools/structo
python -m pytest        # run tests (-m "not slow" skips the memory test)
./structo.py FILE [--path a.b[0].c] [--sample N]   # schema/shape of a data file
./structo.py FILE --select a,b.c   # one TSV row per record, to pipe to awk/sort

cd tools/repoindex
python -m pytest        # run tests (58 tests against tests/fixtures/repo/)
./repoindex.py build     # full index -> .repoindex/index.db
./repoindex.py update    # incremental (mtime/hash change detection)
./repoindex.py status    # freshness + per-language file/symbol counts
./repoindex.py sql "SELECT ..."   # read-only escape hatch, column-aligned

# tools/rq and tools/testmap are retired from default use (0006). Still
# implemented and tested (`python -m pytest` in either dir); read their
# STATUS.md before changing them, don't reach for them mid-task.

cd tools/codediff
python -m pytest        # run tests (38 tests; scripted temp repos, needs git + sibling repoindex)
./codediff.py [REF|A..B] [--staged] [--json] [--max-tokens N]   # semantic diff summary
```

All are stdlib-only Python, single-file except `repoindex` (a package).
Shared behaviour: stdout **and stderr** pinned to UTF-8 at entry; offline
and deterministic; `--max-tokens` on by default (`sgrep` 1500,
`xread`/`structo`/`gitbrief` 2000, `repomap`/`codediff` 3000; `0` =
unbounded; `structo --select`/`--raw` and `codediff --json` exempt from the
default, not from an explicit cap).

Per-tool design rationale lives in each `tools/<name>/DECISIONS.md` and
current state in its `STATUS.md` — read those rather than restating them
here. What bites you if you don't know it:

| tool | gotcha |
|---|---|
| `tokq` | uses `tiktoken` (o200k_base) if installed, else a bytes/3.7 heuristic; always states which. |
| `runlite` | passes the wrapped command's exit code through; 125/127 are reserved for its own failures. |
| `xread` | Python via `ast`; JS/TS, markdown and Prisma via heuristic scanners, so spans can be approximate. |
| `sgrep` | needs the `rg` binary at runtime (PATH, `--rg`, or `SGREP_RG`). Exits 1 on no matches, 2 on error. |
| `repomap` | `--focus PATH` narrows, it does not merely rank: everything outside the focus collapses to one line. |
| `gitbrief` | read-only git plumbing; renames off, `--no-optional-locks`. Git discovery stops at `$HOME` so a run outside a project can't adopt a dotfiles repo and scan your home tree (`GITBRIEF_NO_CEILING=1` overrides). |
| `structo` | streams everything (memory O(schema+samples)). `--select`/`--raw` **refuse rather than truncate** when over an explicit budget — they feed `awk`/`sort`, not context. A leading `[N]` in `--path` picks JSONL record N. |
| `repoindex` | `extract()` is pure and filesystem-free (`codediff` reuses it on git blobs). Every ref is tagged `resolved` or `heuristic`, never dropped. `update` is incremental and preserves `testmap record` coverage rows. |
| `codediff` | there is no `--llm` flag — `--json` **is** the narrator payload. Risk is a flat list of explainable flags, never a grade (0002). Same `$HOME` git ceiling as `gitbrief` (`CODEDIFF_NO_CEILING=1`). Exit 0 ok, 2 usage/git error. |

For any other tool, there is nothing to run yet — start from that tool's `PRD.md` and the corresponding bootstrap prompt in `START.md`, and follow the suite-wide conventions above plus `INVARIANTS.md`.

## Notes on repo state

- Git repository since 2026-07-10; remote: `github.com/illpro226/LLM-tools` (private). Commit style per `AGENTS.md`: short, imperative subjects (`add xread token cap tests`).
- `.claude/settings.local.json` contains an allowlist scoped to `tokq` development (pytest, tiktoken checks, venv setup) — it's specific to work already done there, not a general policy.
