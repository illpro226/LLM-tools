# STATUS — LLM-tools

Last updated: 2026-09-11

Written to be read by an agent starting cold. Keep it under a screen. Each
tool's own `tools/<name>/STATUS.md` is the authority on that tool — this file is
the suite.

## Works

- **Nine tools are live:** `tokq`, `runlite`, `xread`, `sgrep`, `repomap`,
  `gitbrief`, `structo`, `repoindex`, `codediff`. `repoindex` is live both as the
  library behind `codediff` and as a CLI.
- All are stdlib-only Python, single-file except `repoindex`. Offline and
  deterministic; stdout and stderr pinned to UTF-8 at entry.
- Token budgets are on by default with `--max-tokens 0` as the escape hatch
  (`docs/decisions/0005`). Every tool that can grow degrades by summarising
  harder, never by truncating mid-thought.
- Shims in `bin/` put every tool on PATH for cmd/PowerShell and Git Bash/WSL.
- **The build list is closed** (`docs/decisions/0003`). `rq` and `testmap` were
  built, measured as never reached for, and archived (`0009`).
- As of this adoption the repo carries the CFS contract: `AGENTS.md` is the
  contract at 80 lines, `CLAUDE.md` is one line, all six doc kinds exist, and
  both gates run.

## Broken / stale

- **`CLAUDE.md` had been duplicating `AGENTS.md` and `INVARIANTS.md` for
  weeks.** Its "Suite-wide conventions" section restated rules that
  `INVARIANTS.md` already held as the authority — two copies of a rule, one of
  them loaded every turn. Removed rather than merged.
- **`--sweep` in CFS-SPEC reported this repo as already migrated** because
  `AGENTS.md` had a routing table. It did not have the gates, and the 98-line
  `CLAUDE.md` was still being loaded. Fixed upstream in CFS-SPEC DEC-0011; the
  half-adoption is what this commit closes.
- **`docs/decisions/0004`** accepts an MCP stdio adapter for
  `xread`/`sgrep`/`structo`/`gitbrief`. It is planned in `mcp/` and **not
  built**.
- `START.md` is historical. It describes what each tool was originally for, not
  what it does now, and carries its own banner saying so. Nobody has decided
  whether it should be archived.
- `doc/` still exists as a compatibility alias for `docs/`. Nothing has been
  moved out of it and nothing has decided when it goes away.
- The suite has no repo-wide test command. Running everything means visiting
  nine directories, so nobody does it, and there is no recorded run of all nine
  suites passing at the same commit.

## Next

- Decide whether the MCP adapter (`0004`) is still wanted, or supersede it. It
  has been accepted-and-unbuilt long enough that the acceptance is stale.
- Give the suite one command that runs every tool's tests, so "all nine pass"
  becomes a thing that can be stated with evidence.
- Retire `doc/` and `START.md`, or write down why they stay.
