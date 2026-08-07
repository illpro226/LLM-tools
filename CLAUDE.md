# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

LLM-tools is a toolkit of small, composable CLI utilities that help coding agents (Claude Code, aider, etc.) spend fewer tokens per task. The unifying idea: never put raw, bulky content into an agent's context when a compressed, targeted view will do.

Nine tools are live: `tokq`, `runlite`, `xread`, `sgrep`, `repomap`, `gitbrief`, `structo`, `repoindex`, `codediff`. `repoindex` is live as the library behind `codediff` as well as a CLI. `rq` and `testmap` were built and then archived to `archive/` for never being reached for (0009) — off PATH, not reachable mid-task.

The build list is closed (0003): no Wave 5, and `factbook`/`docsnip` are deferred indefinitely, revivable only on recorded dogfooding evidence. A tool's `STATUS.md` is the authority on its current state.

- [`START.md`](START.md) — canonical description of every tool in the suite plus its bootstrap prompt. Read this before starting a new tool.
- [`INVARIANTS.md`](INVARIANTS.md) — rules that hold across every tool (output, semantics, performance, docs). A change that breaks one needs a decision record in `docs/decisions/`, not just a PR.
- `docs/decisions/` — the binding record; read one before changing what it
  settled. The ones that constrain current work: **0003** closes the build
  list · **0005** token budgets on by default · **0007** savings-log
  operations (no repeat-call memo; compact `events.jsonl` only past 4 MB /
  50 ms) · **0004** accepts an MCP stdio adapter for
  xread/sgrep/structo/gitbrief (planned in `mcp/`, not built). 0001, 0002,
  0006, 0008 and 0009 record how the suite got here; read them for
  rationale, not rules. START.md's 14-tool list is superseded by 0001.
- `docs/README.md`, `docs/PRDs/README.md`, `docs/known-issues/README.md` —
  index pages; per-tool PRDs live at `tools/<name>/PRD.md`.
- `doc/` is a compatibility alias for `docs/` — put new documentation in `docs/`, not `doc/`. Doc links are repo-relative; keep them that way.

## Dogfood the suite while working here

When working in this repo, prefer the suite's own tools over built-ins for the
jobs they cover — real usage is the field test fixtures can't provide:

- `xread FILE --symbol NAME` instead of reading a whole file for one function;
  `--query` for docs. `--headings` outlines one file — markdown headings, or
  a code file's symbols with their spans — and is the cheap first move on an
  unfamiliar file, since `--symbol` needs a name you don't have yet.
- `repomap` for orientation after a compaction or when entering an unfamiliar
  part of the repo, instead of `ls` + reading CLAUDE.md sections.
- `structo` for any JSON/YAML/JSONL/XML you'd otherwise read raw; when the
  question is about *values* across records rather than shape, `structo
  FILE --select f1,f2 | awk ...` instead of a throwaway analysis script.
- `runlite trace FILE` (or piped) whenever a stack trace turns up in a log,
  in CI output, or in something the user pasted — anywhere you did not run
  the command yourself. Reading a raw traceback is the thing it replaces.
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
finishing ritual on every doc edit.

Whenever a built-in was genuinely easier or a tool's output missed what you
needed, file it in `docs/known-issues/` (one file per issue). That friction
is the product feedback this section exists to collect — it is what
archived two working tools (0009) and what any revival would need.

## Suite-wide conventions (apply to every tool)

- One directory per tool: `tools/<name>/`, each a standalone CLI installable on PATH.
- Plain-text, deterministic output meant to be read by an LLM: compact, stable ordering, no ANSI color, no spinners, no timestamps in normal output.
- Every line that makes a claim about code carries a `path:line` reference so a finding can be followed up with `xread`.
- Every tool whose output can grow supports `--max-tokens N` (or `--max-bytes`), degrading by summarizing harder — never by truncating mid-thought. The budget is **on by default** (docs/decisions/0005) with `--max-tokens 0` as the escape hatch; every rung of a ladder must be bounded, not merely smaller; and any degradation that removes what was asked for says so and names the flag. Modes that feed another program (`structo --select`/`--raw`, `--json` payloads) are exempt from the default, never from an explicit cap.
- Prefer Python or Go, minimal dependencies, fast startup (~100ms budget on the no-heavy-deps path).
- Offline and deterministic by default: any LLM call is opt-in behind an explicit flag and never receives raw source/diffs, only the tool's own compact structured summary.
- Confidence is two-valued (`resolved` | `heuristic`), never an ordinal HIGH/MEDIUM/LOW scale — static analysis can't honestly support finer grades.
- Relationship-shaped queries go through the shared `.repoindex/index.db` rather than re-parsing source (this was `rq`'s job before it was archived — docs/decisions/0009; `repoindex` itself still owns the schema); excerpt/orientation tools (`xread`, `sgrep`, `repomap`) parse directly and must keep working when no index exists.

## Working in a tool directory

There's no repo-wide build system; each tool is self-contained: `cd tools/<name> && python -m pytest`. Run a tool with `./<name>.py` (chmod +x first) or `python <name>.py`; `--help` carries the current flags, so they are not restated here. Archived tools test the same way from `archive/rq/` and `archive/testmap/`.

Test-suite quirks worth knowing before you run one:

| tool | note |
|---|---|
| `runlite` | canned-log and canned-trace fixtures; no real toolchains needed. |
| `sgrep` | real-`rg` tests skip when `rg` is absent. |
| `gitbrief`, `codediff` | build temp repos; need `git` on PATH (`codediff` also needs the sibling `repoindex` importable). |
| `structo` | `-m "not slow"` skips the memory test. |

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
| `runlite` | passes the wrapped command's exit code through; 125/127 are reserved for its own failures. `trace` wraps nothing, so it uses its own: 0 distilled, 1 no recognizable trace, 125 internal. |
| `xread` | Python via `ast`; JS/TS, markdown and Prisma via heuristic scanners, so spans can be approximate. |
| `sgrep` | needs the `rg` binary at runtime (PATH, `--rg`, or `SGREP_RG`). Exits 1 on no matches, 2 on error. |
| `repomap` | `--focus PATH` narrows, it does not merely rank: everything outside the focus collapses to one line. |
| `gitbrief` | read-only git plumbing; renames off, `--no-optional-locks`. Git discovery stops at `$HOME` so a run outside a project can't adopt a dotfiles repo and scan your home tree (`GITBRIEF_NO_CEILING=1` overrides). |
| `structo` | streams everything (memory O(schema+samples)). `--select`/`--raw` **refuse rather than truncate** when over an explicit budget — they feed `awk`/`sort`, not context. A leading `[N]` in `--path` picks JSONL record N. |
| `repoindex` | `extract()` is pure and filesystem-free (`codediff` reuses it on git blobs). Every ref is tagged `resolved` or `heuristic`, never dropped. `update` is incremental. |
| `codediff` | there is no `--llm` flag — `--json` **is** the narrator payload. Risk is a flat list of explainable flags, never a grade (0002). Same `$HOME` git ceiling as `gitbrief` (`CODEDIFF_NO_CEILING=1`). Exit 0 ok, 2 usage/git error. |

## Notes on repo state

- Git repository since 2026-07-10; remote: `github.com/illpro226/LLM-tools` (public since 2026-08-07 — treat anything committed here as published). Commit style per `AGENTS.md`: short, imperative subjects (`add xread token cap tests`).
- `.claude/settings.local.json` contains an allowlist scoped to `tokq` development (pytest, tiktoken checks, venv setup) — it's specific to work already done there, not a general policy.
