# Adopt the suite in another project

This is the copy-paste block. Drop it into any project's `AGENTS.md`, or into
your agent's global instructions, to make that project use LLM-tools. It is kept
out of this repo's own `AGENTS.md` on purpose: an agent working *here* already
knows the tools, and this block exists for everywhere else.

Keep it self-contained. If you add a tool or change a flag, edit it here.

---

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
| `cat` on JSON/YAML/TOML/JSONL/XML/CSV/logs | `structo` | `structo data.json --path items[0]` |
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
