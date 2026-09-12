# AGENTS.md — LLM-tools

A suite of small CLI utilities that let a coding agent spend fewer tokens per
task: never put raw, bulky content into context when a compressed, targeted view
will do. Nine tools are live; `rq` and `testmap` were built, then archived for
never being reached for (`docs/decisions/0009`).

## Routing table — read only what the task needs

| If the task is… | Read | Do not read |
|---|---|---|
| A tool's quirks, exit codes, defaults, env vars | `docs/reference/REF-tool-gotchas.md` | the tool's source first |
| Making another project use the suite | `docs/reference/REF-adopt-the-suite.md` (the copy-paste block) | this file |
| A rule that holds across every tool | `INVARIANTS.md` | any single tool |
| "Why is it like this?" — suite-wide | `docs/decisions/` (binding) | git history |
| "Why is it like this?" — one tool | `tools/<name>/DECISIONS.md` | `docs/decisions/` |
| What a tool does today, and its test count | `tools/<name>/STATUS.md` (the authority) | `START.md` |
| Current state of the suite | `STATUS.md` | `CHANGELOG.md` |
| A tool that misbehaved | `docs/known-issues/` — file it there | — |
| What each tool was originally for | `START.md` (historical, not current) | — |

`doc/` is a compatibility alias for `docs/` — put new documentation in `docs/`,
and keep doc links repo-relative.

## Commands

```
setup:  (none — stdlib-only Python, no install step; there is no linter)
test:   python -m pytest tools/xread
status: python scripts/check_status.py .
env:    python scripts/check_env.py .
```

No repo-wide build system: `cd tools/<name>` then `python -m pytest`, and
archived tools the same way from `archive/rq/` and `archive/testmap/`. `--help`
carries the current flags, so they are not restated anywhere.

## Environment — what a cold agent would otherwise have to discover

- Toolchain: `python` and `git`. `rg` is needed at runtime by `sgrep` only.
- All tools are stdlib-only Python, single-file except `repoindex` (a package).
- Three environment variables exist and none is a secret: `SGREP_RG`,
  `GITBRIEF_NO_CEILING`, `CODEDIFF_NO_CEILING`. **Nothing loads a `.env`** and
  there is deliberately no `.env.example` — see `docs/decisions/0010`.
- The tools are on PATH via shims in `bin/` — `.cmd` for cmd/PowerShell,
  extensionless `sh` for Git Bash/WSL (new shells only). If a name is not
  recognised, run `python tools/<name>/<name>.py` from this repo.
- **The remote is public.** `github.com/illpro226/LLM-tools`, public since
  2026-08-07 — treat anything committed here as published.

## Boundaries

- **The build list is closed** (`docs/decisions/0003`): no Wave 5, and
  `factbook`/`docsnip` are deferred indefinitely, revivable only on recorded
  dogfooding evidence.
- **Breaking an invariant needs a decision record**, not just a PR.
  `INVARIANTS.md` holds the suite-wide rules — output, semantics, performance,
  docs — and is the authority; do not restate them elsewhere.
- A change to a tool's behaviour updates its `CHANGELOG.md` and `STATUS.md`
  (version, test count) **in the same commit**. `STATUS.md` is the only place a
  test count is stated, so there is nothing to keep in sync.
- One directory per tool, `tools/<name>/`, each a standalone CLI installable on
  PATH. Prefer Python or Go, minimal deps, ~100ms startup. Never commit
  `.repoindex/` or other rebuildable state. `docs/decisions/` is append-only.

## Done means

The tool was actually run and its real output shown, and its own `pytest` suite
passed. Cap and degrade paths count as behaviour: a change that can grow output
is not done until a bounded run is in the evidence.

## Gotchas

- **Dogfood the suite while working here.** It is the field test fixtures cannot
  provide. When a built-in was genuinely easier, or a tool's output missed what
  you needed, file it in `docs/known-issues/` — that friction is the feedback
  that archived two working tools (`0009`), and any revival would need it.
- Commit subjects are short and imperative:
  `fix xread --query markdown section swallowing (xread v0.1.1)`.
- PRs note the commands run for verification, and any new flags or artifacts.
