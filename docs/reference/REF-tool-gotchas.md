# Per-tool gotchas and test quirks

Moved out of `CLAUDE.md` when the suite adopted the CFS structure, unchanged.
These were being loaded on every turn of every session, including the many that
touched one tool or none.

Per-tool design rationale lives in each `tools/<name>/DECISIONS.md` and current
state in its `STATUS.md`. This file holds only what bites you if you do not know
it in advance.

## What bites you

| tool | gotcha |
|---|---|
| `tokq` | Uses `tiktoken` (o200k_base) if installed, else a bytes/3.7 heuristic; always states which. |
| `runlite` | Passes the wrapped command's exit code through; 125/127 are reserved for its own failures. `trace` wraps nothing, so it uses its own: 0 distilled, 1 no recognizable trace, 125 internal. |
| `xread` | Python via `ast`; JS/TS, markdown and Prisma via heuristic scanners, so spans can be approximate. |
| `sgrep` | Needs the `rg` binary at runtime (PATH, `--rg`, or `SGREP_RG`). Exits 1 on no matches, 2 on error. |
| `repomap` | `--focus PATH` **narrows, it does not merely rank**: everything outside the focus collapses to one line. |
| `gitbrief` | Read-only git plumbing; renames off, `--no-optional-locks`. Git discovery stops at `$HOME`, so a run outside a project cannot adopt a dotfiles repo and scan your home tree (`GITBRIEF_NO_CEILING=1` overrides). |
| `structo` | Streams everything (memory O(schema+samples)). `--select`/`--raw` **refuse rather than truncate** when over an explicit budget — they feed `awk`/`sort`, not context. A leading `[N]` in `--path` picks JSONL record N. |
| `repoindex` | `extract()` is pure and filesystem-free (`codediff` reuses it on git blobs). Every ref is tagged `resolved` or `heuristic`, never dropped. `update` is incremental. |
| `codediff` | There is no `--llm` flag — `--json` **is** the narrator payload. Risk is a flat list of explainable flags, never a grade (decision 0002). Markdown gets a structural pass (headings/fenced code), not a symbol one (ADR-009); what is still unanalyzed is reported as a share of the change, so read that line before trusting the summary as complete. Same `$HOME` git ceiling as `gitbrief` (`CODEDIFF_NO_CEILING=1`). Exit 0 ok, 2 usage/git error. |

## Test-suite quirks

Each tool is self-contained: `cd tools/<name>` then `python -m pytest`. Archived
tools test the same way from `archive/rq/` and `archive/testmap/`.

| tool | note |
|---|---|
| `runlite` | Canned-log and canned-trace fixtures; no real toolchains needed. |
| `sgrep` | Real-`rg` tests skip when `rg` is absent. |
| `gitbrief`, `codediff` | Build temp repos; need `git` on PATH (`codediff` also needs the sibling `repoindex` importable). |
| `structo` | `-m "not slow"` skips the memory test. |

## Default token budgets

Budgets are on by default (`docs/decisions/0005`); `--max-tokens 0` is the escape
hatch.

| tool | default `--max-tokens` |
|---|---|
| `sgrep` | 1500 |
| `xread`, `structo`, `gitbrief` | 2000 |
| `repomap`, `codediff` | 3000 |

All tools are stdlib-only Python, single-file except `repoindex` (a package).
Stdout **and** stderr are pinned to UTF-8 at entry; every tool is offline and
deterministic.

## Environment variables

There is no `.env` file and nothing loads one. These are behaviour toggles read
directly from the process environment, and none is a secret:

| variable | tool | effect |
|---|---|---|
| `SGREP_RG` | `sgrep` | Path to the `rg` binary, when it is not on PATH. Also settable with `--rg`. |
| `GITBRIEF_NO_CEILING` | `gitbrief` | Lifts the `$HOME` git-discovery ceiling. |
| `CODEDIFF_NO_CEILING` | `codediff` | The same, for `codediff`. |

See `docs/decision/DEC-0001-no-env-example.md` for why there is no
`.env.example` despite the audit asking for one.
