# STATUS — LLM-tools

Last updated: 2026-10-08

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
- `python scripts/test_all.py` runs every suite in parallel and states the
  result in one screen: all nine pass, 548 tests, 2026-10-09.
- The 2026-10-08 review's 24 known issues and 9 older ones are fixed and
  archived (2026-10-09), each pinned by a test that fails on the previous
  version. Among them: codediff filed a URL swap as a comment-only edit;
  runlite and tokq now budget by default (`docs/decisions/0011`);
  `gitbrief show COMMIT`, `structo -` (stdin) and `sgrep --plain` are new;
  `str.splitlines()` line drift is gone from five tools. Each tool's
  CHANGELOG has the details. One issue stays open on purpose:
  `bounded-builtin-calls-treated-as-equivalent-to-sgrep` waits on usage
  data, not code.
- A review on 2026-09-24 fixed bugs in all nine tools — among them
  an sgrep budget loop quadratic in matching files (8 minutes at 20,000),
  an sgrep stderr deadlock, structo and xread misreading UTF-8 BOM files,
  gitbrief's `+0 -0` counts from a subdirectory, runlite `trace` inventing
  exception chains, and budget floors in five tools that were still
  O(input); each tool's CHANGELOG has its entry.

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

## Next

- Decide whether the MCP adapter (`0004`) is still wanted, or supersede it. It
  has been accepted-and-unbuilt long enough that the acceptance is stale.
- Retire `doc/` and `START.md`, or write down why they stay.
- Deploy `hooks/llm-tools-guard.py` to `~/.claude/hooks` (its grep
  message now names `sgrep --plain`); the live copy predates it.
- Review follow-ups (suggestions, not decided):
  - One shared copy of duplicated code, or a test that fails when copies
    differ. The JS scanner is in 4 tools, and `_git`/`fit` are repeated.
    Two of the bugs were copies drifting.
  - A shared odd-input fixture set (BOM, CRLF, `\f`, spaces/quotes in
    paths, binary, empty) run against every tool.
  - One suite rule: exit 0 = found, 1 = none, 2 = error, never a traceback.
    Each `main` catches everything.
  - NUL-separated git output (`-z`) in gitbrief's status/numstat parses
    (codediff's are done).
  - Only sgrep and `structo --select` write `\n` on Windows; every other
    tool's stdout still writes `\r\n`.
