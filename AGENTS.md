# AGENTS.md — LLM-tools

LLM-tools is a suite of small CLI utilities that let a coding agent spend
fewer tokens per task: never put raw, bulky content into context when a
compressed, targeted view will do. Nine tools are live; `rq` and `testmap`
were built, then archived for never being reached for (docs/decisions/0009)
and now live in `archive/`. `START.md` describes each tool; `INVARIANTS.md` holds the rules
every tool must keep; each tool lives in `tools/<name>/` with its own
docs (`STATUS.md`, `CHANGELOG.md`, `DECISIONS.md`) and `tests/`.

## Use these tools instead of built-ins

The section below is self-contained — copy it into any project's
AGENTS.md (or your agent's global instructions) to adopt the suite there.

The tools are on PATH via the shims in `bin/` — `.cmd` for
cmd/PowerShell, extensionless `sh` scripts for Git Bash/WSL/POSIX
(new shells only). If a name isn't recognized, call the shim by full
path or run `python tools/<name>/<name>.py` from this repo.

| Instead of | Use | Example |
|---|---|---|
| Reading a whole file for one function or section | `xread` | `xread app.py --symbol Login.validate`, `xread doc.md --headings`, then `--query "text"` or `--lines 40-80 --scope` |
| `ls -R` / reading many files to get oriented | `repomap` | `repomap . --focus src/auth` |
| Raw `grep`/`rg` dumps | `sgrep` (needs `rg` on PATH) | `sgrep "retry" src --counts-only` |
| Running a build/test and reading the full log | `runlite` | `runlite -- python -m pytest -q` |
| `cat` on JSON/YAML/JSONL/XML/CSV/logs | `structo` | `structo data.json --path items[0]` |
| Raw `git diff` / `git log` / `git status` | `gitbrief` | `gitbrief`, `gitbrief hunks`, `gitbrief show FILE`, `gitbrief log`, `gitbrief pr main` |
| Re-reading hunks to judge what a change means | `codediff` | `codediff --staged` (API/behavior/removed/mechanical + risk flags) |
| Grepping for call sites and relationships | `sgrep` | `sgrep "LoginManager" --counts-only`, then narrow |
| Guessing what is cheap or expensive to read | `tokq` | `tokq FILE`, `tokq dir .`, `tokq lint docs\` |

Shared behavior you can rely on: output is plain, deterministic text
meant to be read by an LLM; every claim line carries a `path:line` you
can follow up with `xread`; every tool accepts `--max-tokens N` and
degrades by summarizing harder, never truncating mid-thought (budgets are
on by default; `--max-tokens 0` is the escape hatch). `codediff` reads the
shared `.repoindex/index.db` for test-coverage flags when one exists, and
runs without it, saying what is missing — build it with `repoindex build`
if you want those flags. Confidence in index-backed answers is two-valued —
`resolved` or `heuristic` — treat heuristic edges as leads, not facts.
Caveats: `sgrep` errors clearly if `rg` is absent; `tokq` falls back to
a bytes-based estimate without `tiktoken` and says so.

## Working in this repo

- Dogfood the suite while working here; it is the field test fixtures
  can't provide. When a built-in was genuinely easier or a tool's output
  missed what you needed, file it in `docs/known-issues/` (one file per
  issue: what breaks, when, expected, workaround).
- Each tool is self-contained: `cd tools\<name>` then `python -m pytest`.
  All are stdlib-only Python; every tool except `repoindex` (a package)
  is a single file.
- A change to a tool's behavior updates its `CHANGELOG.md` and
  `STATUS.md` (version, test count) in the same commit; cross-tool rules
  live in `INVARIANTS.md`, and breaking one needs a decision record in
  `docs/decisions/`, not just a PR. `STATUS.md` is the only place a test
  count is stated, so there is nothing to keep in sync.
- `tokq lint`/`tokq dir` when deciding what to cut from a document or
  hunting where token weight lives — not a finishing ritual on every edit.

## Style, tests, commits

- Keep output deterministic: stable ordering, no ANSI color, no
  timestamps in normal output; support `--max-tokens` on anything that
  can grow (see `INVARIANTS.md` for the full list).
- Tests are fixture-based and assert real command output; name them
  after behavior; cover cap/degrade paths and determinism.
- Commit subjects are short and imperative, e.g.
  `fix xread --query markdown section swallowing (xread v0.1.1)`.
- PRs note the commands run for verification and any new flags or
  generated artifacts. Never commit `.repoindex/` or other rebuildable
  state.
