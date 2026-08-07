# LLM-tools

Small, composable CLI tools that keep raw, bulky content out of an LLM
coding agent's context — a compressed, targeted view instead of a whole
file, a full `git diff`, or a wall of test output. Nine tools, all
implemented and tested, all standalone (stdlib-only Python). Two more,
`rq` and `testmap`, were built and tested but are archived after a month
of near-zero use (docs/decisions/0009) — code kept in `archive/`, not
installed.

## Requirements

- Python 3.9+ on PATH (as `python` or `python3`)
- Git (for `gitbrief`, `codediff`, `repoindex`)
- [ripgrep](https://github.com/BurntSushi/ripgrep) on PATH — only needed for `sgrep`
- Optional: [`tiktoken`](https://github.com/openai/tiktoken) for exact token counts in `tokq` (falls back to a bytes-based estimate without it, and says so)

No other dependencies. Nothing to build or install via pip/npm.

## Install

```sh
git clone https://github.com/illpro226/LLM-tools.git
```

Add the repo's `bin/` directory to your `PATH`:

- **Windows (PowerShell):**
  ```powershell
  $env:PATH += ";C:\path\to\LLM-tools\bin"   # current session
  # persist: System Properties -> Environment Variables -> add to PATH
  ```
- **Git Bash / WSL / macOS / Linux:**
  ```sh
  echo 'export PATH="$PATH:/path/to/LLM-tools/bin"' >> ~/.bashrc   # or ~/.zshrc
  ```

`bin/` ships two shims per tool: a `.cmd` for cmd.exe/PowerShell and an
extensionless POSIX shell script for Git Bash/WSL — both just invoke
`python tools/<name>/<name>.py`. If a shell doesn't pick up the shim
(e.g. Windows `cmd.exe` needs the `.cmd` extension, which it resolves
automatically once `bin/` is on `PATH`), call the tool directly:

```sh
python /path/to/LLM-tools/tools/xread/xread.py FILE --symbol NAME
```

Verify the install:

```sh
tokq --help
```

## The tools

| Tool | What it's for | Example |
|---|---|---|
| `xread` | Read one function/section of a file, not the whole thing | `xread app.py --symbol Login.validate` |
| `repomap` | Orient in an unfamiliar repo: tree + ranked symbol outline | `repomap . --focus src/auth` |
| `sgrep` | Ranked, deduped search results instead of a raw `rg` dump | `sgrep "retry" src --counts-only` |
| `runlite` | Run a build/test command, get a failure-focused report | `runlite -- python -m pytest -q` |
| `structo` | Schema/shape of a JSON/YAML/JSONL/XML/CSV file, not its contents | `structo data.json --path items[0]` |
| `gitbrief` | Layered git views (status, hunks, log, PR summary) | `gitbrief`, `gitbrief pr main` |
| `codediff` | What a change *means* — API/behavior/removed/mechanical + risk flags | `codediff --staged` |
| `tokq` | Token cost meter — flags context-wasteful files before you read them | `tokq dir .`, `tokq lint docs/` |
| `repoindex` | Shared symbol/relationship index (`.repoindex/index.db`) that `codediff` builds on | `repoindex build` |

`rq` (query the index) and `testmap` (map changed files to covering
tests) are archived — see `archive/rq/`, `archive/testmap/`, and
docs/decisions/0009.

Every tool prints plain, deterministic text with `path:line` references
you can follow up on, and accepts `--max-tokens N` to cap output size
(`0` = unbounded). Run `<tool> --help` for full usage.

## Using this with a coding agent

[`AGENTS.md`](AGENTS.md) has a copy-pasteable section ("Use these tools
instead of built-ins") for dropping into any project's `AGENTS.md` or
your agent's global instructions, so it reaches for these tools instead
of raw `cat`/`grep`/`git diff`.

## Repo layout

- `tools/<name>/` — one directory per tool, each with its own `README.md`,
  `STATUS.md`, `CHANGELOG.md`, tests, and design docs
- `bin/` — PATH shims
- `docs/` — cross-tool documentation: [`docs/decisions/`](docs/decisions/)
  (binding architecture/scope decisions), [`docs/PRDs/`](docs/PRDs/),
  [`docs/known-issues/`](docs/known-issues/)
- [`INVARIANTS.md`](INVARIANTS.md) — rules every tool must hold
- [`START.md`](START.md) — original per-tool spec and bootstrap prompts

## Contributing

See [`AGENTS.md`](AGENTS.md) for conventions, working-in-a-tool-directory
commands, and review expectations.

## License

[MIT](LICENSE)
